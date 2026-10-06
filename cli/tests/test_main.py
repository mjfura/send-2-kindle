import smtplib
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from send_2_kindle import installed_version
from send_2_kindle.main import app
from tests.fakes import FakeSMTPServer

runner = CliRunner()


def _file(directory: Path, name: str, content: bytes = b"data") -> Path:
    path = directory / name
    path.write_bytes(content)
    return path


def _send(*paths: Path) -> list[str]:
    return ["send", *(str(path) for path in paths)]


def _subjects(server: FakeSMTPServer) -> list[str]:
    return [str(message["Subject"]) for message in server.sent]


@pytest.mark.usefixtures("valid_env")
def test_sends_every_valid_file(fake_smtp: FakeSMTPServer, tmp_path: Path) -> None:
    result = runner.invoke(app, _send(_file(tmp_path, "a.epub"), _file(tmp_path, "b.pdf")))
    assert result.exit_code == 0, result.output
    assert "2 sent, 0 failed" in result.output
    assert "Amazon may still reject" in result.output
    assert _subjects(fake_smtp) == ["a.epub", "b.pdf"]


@pytest.mark.usefixtures("valid_env")
def test_invalid_file_is_reported_and_others_are_sent(
    fake_smtp: FakeSMTPServer, tmp_path: Path
) -> None:
    result = runner.invoke(app, _send(_file(tmp_path, "a.epub"), _file(tmp_path, "b.mobi")))
    assert result.exit_code == 1
    assert "unsupported extension" in result.output
    assert "1 sent, 1 failed" in result.output
    assert _subjects(fake_smtp) == ["a.epub"]


@pytest.mark.usefixtures("valid_env")
def test_does_not_connect_when_no_file_is_valid(fake_smtp: FakeSMTPServer, tmp_path: Path) -> None:
    result = runner.invoke(app, _send(tmp_path / "missing.pdf"))
    assert result.exit_code == 1
    assert "file not found" in result.output
    assert "0 sent, 1 failed" in result.output
    assert "Amazon may still reject" not in result.output
    assert fake_smtp.calls == []


def test_config_error_exits_2_without_connecting(fake_smtp: FakeSMTPServer, tmp_path: Path) -> None:
    result = runner.invoke(app, _send(_file(tmp_path, "a.epub")))
    assert result.exit_code == 2
    assert "S2K_KINDLE_EMAIL" in result.output
    assert fake_smtp.calls == []


@pytest.mark.usefixtures("valid_env")
def test_auth_failure_aborts_and_marks_files_not_sent(
    fake_smtp: FakeSMTPServer, tmp_path: Path
) -> None:
    fake_smtp.login_error = smtplib.SMTPAuthenticationError(535, b"bad credentials")
    result = runner.invoke(app, _send(_file(tmp_path, "a.epub"), _file(tmp_path, "b.pdf")))
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
    result = runner.invoke(app, _send(_file(tmp_path, "a.epub"), _file(tmp_path, "b.pdf")))
    assert result.exit_code == 1
    assert "552 message too large" in result.output
    assert "1 sent, 1 failed" in result.output
    assert _subjects(fake_smtp) == ["b.pdf"]


@pytest.mark.usefixtures("valid_env")
def test_connection_lost_mid_run_marks_remaining_files_not_sent(
    fake_smtp: FakeSMTPServer, tmp_path: Path
) -> None:
    fake_smtp.send_errors["a.epub"] = smtplib.SMTPServerDisconnected("gone")
    result = runner.invoke(app, _send(_file(tmp_path, "a.epub"), _file(tmp_path, "b.pdf")))
    assert result.exit_code == 1
    assert "connection lost" in result.output
    assert "0 sent, 2 failed" in result.output
    assert _subjects(fake_smtp) == []


def test_send_requires_at_least_one_file() -> None:
    result = runner.invoke(app, ["send"])
    assert result.exit_code == 2


def test_files_without_subcommand_are_not_sent(fake_smtp: FakeSMTPServer, tmp_path: Path) -> None:
    result = runner.invoke(app, [str(_file(tmp_path, "a.epub"))])
    assert result.exit_code == 2
    assert fake_smtp.calls == []


def test_no_arguments_shows_help_with_send_command() -> None:
    result = runner.invoke(app, [])
    assert "send" in result.output
    assert "Usage" in result.output


def test_version_option_prints_installed_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == f"s2k {installed_version()}"


def test_installed_version_matches_pyproject() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text())["project"]["version"]
    assert installed_version() == declared
