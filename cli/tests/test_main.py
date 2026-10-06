import errno
import smtplib
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from send_2_kindle import installed_version
from send_2_kindle import mailer as mailer_module
from send_2_kindle import main as main_module
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


def _big(directory: Path, name: str, size: int) -> Path:
    path = directory / name
    with path.open("wb") as handle:
        handle.write(b"%PDF")
        handle.truncate(size)
    return path


@pytest.mark.usefixtures("valid_env")
def test_icloud_limit_applies_to_icloud_senders(
    fake_smtp: FakeSMTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("S2K_SMTP_HOST", "smtp.mail.me.com")
    result = runner.invoke(app, _send(_big(tmp_path, "big.pdf", 16_200_000)))
    assert result.exit_code == 1
    assert "the limit for iCloud (16.2 MB)" in result.output
    assert fake_smtp.calls == []


@pytest.mark.usefixtures("valid_env")
def test_gmail_limit_is_18_mb(fake_smtp: FakeSMTPServer, tmp_path: Path) -> None:
    result = runner.invoke(app, _send(_big(tmp_path, "big.pdf", 18_500_000)))
    assert "the limit for Gmail" in result.output


@pytest.mark.usefixtures("valid_env")
def test_cloud_file_download_is_announced(
    fake_smtp: FakeSMTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main_module, "is_not_downloaded", lambda path: path.name == "cloud.pdf")
    result = runner.invoke(app, _send(_file(tmp_path, "cloud.pdf")))
    assert result.exit_code == 0, result.output
    assert 'Downloading "cloud.pdf" from iCloud…' in result.output


@pytest.mark.usefixtures("valid_env")
def test_oversized_cloud_file_is_rejected_before_download(
    fake_smtp: FakeSMTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main_module, "is_not_downloaded", lambda path: True)
    result = runner.invoke(app, _send(_big(tmp_path, "cloud.pdf", 19_000_000)))
    assert "Downloading" not in result.output
    assert "the limit for Gmail" in result.output


@pytest.mark.usefixtures("valid_env")
def test_failed_icloud_download_does_not_stop_other_files(
    fake_smtp: FakeSMTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cloud, local = _file(tmp_path, "cloud.pdf"), _file(tmp_path, "local.pdf")
    monkeypatch.setattr(main_module, "is_not_downloaded", lambda path: path.name == "cloud.pdf")
    monkeypatch.setattr(mailer_module, "is_not_downloaded", lambda path: path.name == "cloud.pdf")
    real_build = mailer_module.build_message

    def build(settings: object, path: Path) -> object:
        if path.name == "cloud.pdf":
            raise OSError(errno.ETIMEDOUT, "Operation timed out")
        return real_build(settings, path)  # type: ignore[arg-type]

    monkeypatch.setattr(mailer_module, "build_message", build)
    result = runner.invoke(app, _send(cloud, local))
    assert result.exit_code == 1
    assert "could not download it from iCloud (are you offline?)" in result.output
    assert "1 sent, 1 failed" in result.output
    assert _subjects(fake_smtp) == ["local.pdf"]


@pytest.mark.usefixtures("valid_env")
def test_icloud_files_are_downloaded_before_connecting(
    fake_smtp: FakeSMTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main_module, "is_not_downloaded", lambda path: path.name == "cloud.pdf")
    monkeypatch.setattr(
        main_module,
        "_fetch_from_icloud",
        lambda path: fake_smtp.calls.append(f"download:{path.name}"),
    )
    result = runner.invoke(app, _send(_file(tmp_path, "cloud.pdf"), _file(tmp_path, "local.pdf")))
    assert result.exit_code == 0, result.output
    assert fake_smtp.calls[0] == "download:cloud.pdf"
    assert fake_smtp.calls[1].startswith("connect:")


@pytest.mark.usefixtures("valid_env")
def test_failed_download_happens_before_connecting(
    fake_smtp: FakeSMTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(path: Path) -> None:
        raise OSError(errno.ETIMEDOUT, "Operation timed out")

    monkeypatch.setattr(main_module, "is_not_downloaded", lambda path: True)
    monkeypatch.setattr(main_module, "_fetch_from_icloud", fail)
    result = runner.invoke(app, _send(_file(tmp_path, "cloud.pdf")))
    assert result.exit_code == 1
    assert "could not download it from iCloud (are you offline?)" in result.output
    assert fake_smtp.calls == []
