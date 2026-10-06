import smtplib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from send_2_kindle.main import app
from tests.fakes import FakeSMTPServer

runner = CliRunner()


def _file(directory: Path, name: str, content: bytes = b"data") -> Path:
    path = directory / name
    path.write_bytes(content)
    return path


def _subjects(server: FakeSMTPServer) -> list[str]:
    return [str(message["Subject"]) for message in server.sent]


@pytest.mark.usefixtures("valid_env")
def test_sends_every_valid_file(fake_smtp: FakeSMTPServer, tmp_path: Path) -> None:
    files = [_file(tmp_path, "a.epub"), _file(tmp_path, "b.pdf")]
    result = runner.invoke(app, [str(path) for path in files])
    assert result.exit_code == 0, result.output
    assert "2 sent, 0 failed" in result.output
    assert "Amazon may still reject" in result.output
    assert _subjects(fake_smtp) == ["a.epub", "b.pdf"]


@pytest.mark.usefixtures("valid_env")
def test_invalid_file_is_reported_and_others_are_sent(
    fake_smtp: FakeSMTPServer, tmp_path: Path
) -> None:
    files = [_file(tmp_path, "a.epub"), _file(tmp_path, "b.mobi")]
    result = runner.invoke(app, [str(path) for path in files])
    assert result.exit_code == 1
    assert "unsupported extension" in result.output
    assert "1 sent, 1 failed" in result.output
    assert _subjects(fake_smtp) == ["a.epub"]


@pytest.mark.usefixtures("valid_env")
def test_does_not_connect_when_no_file_is_valid(fake_smtp: FakeSMTPServer, tmp_path: Path) -> None:
    result = runner.invoke(app, [str(tmp_path / "missing.pdf")])
    assert result.exit_code == 1
    assert "file not found" in result.output
    assert "0 sent, 1 failed" in result.output
    assert "Amazon may still reject" not in result.output
    assert fake_smtp.calls == []


def test_config_error_exits_2_without_connecting(fake_smtp: FakeSMTPServer, tmp_path: Path) -> None:
    result = runner.invoke(app, [str(_file(tmp_path, "a.epub"))])
    assert result.exit_code == 2
    assert "S2K_KINDLE_EMAIL" in result.output
    assert fake_smtp.calls == []


@pytest.mark.usefixtures("valid_env")
def test_auth_failure_aborts_and_marks_files_not_sent(
    fake_smtp: FakeSMTPServer, tmp_path: Path
) -> None:
    fake_smtp.login_error = smtplib.SMTPAuthenticationError(535, b"bad credentials")
    files = [_file(tmp_path, "a.epub"), _file(tmp_path, "b.pdf")]
    result = runner.invoke(app, [str(path) for path in files])
    assert result.exit_code == 1
    assert "authentication failed" in result.output
    assert "not sent" in result.output
    assert "0 sent, 2 failed" in result.output
    assert "app-password" not in result.output


@pytest.mark.usefixtures("valid_env")
def test_send_error_on_one_file_continues_with_the_rest(
    fake_smtp: FakeSMTPServer, tmp_path: Path
) -> None:
    fake_smtp.send_errors["a.epub"] = smtplib.SMTPDataError(552, b"message too large")
    files = [_file(tmp_path, "a.epub"), _file(tmp_path, "b.pdf")]
    result = runner.invoke(app, [str(path) for path in files])
    assert result.exit_code == 1
    assert "552 message too large" in result.output
    assert "1 sent, 1 failed" in result.output
    assert _subjects(fake_smtp) == ["b.pdf"]


@pytest.mark.usefixtures("valid_env")
def test_connection_lost_mid_run_marks_remaining_files_not_sent(
    fake_smtp: FakeSMTPServer, tmp_path: Path
) -> None:
    fake_smtp.send_errors["a.epub"] = smtplib.SMTPServerDisconnected("gone")
    files = [_file(tmp_path, "a.epub"), _file(tmp_path, "b.pdf")]
    result = runner.invoke(app, [str(path) for path in files])
    assert result.exit_code == 1
    assert "connection lost" in result.output
    assert "0 sent, 2 failed" in result.output
    assert _subjects(fake_smtp) == []


def test_requires_at_least_one_file() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 2
