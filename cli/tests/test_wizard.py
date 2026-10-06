import os
import stat
from pathlib import Path

import pytest
from typer.testing import CliRunner

from send_2_kindle import wizard
from send_2_kindle.config import load_settings
from send_2_kindle.main import app
from tests.fakes import FakeSMTPServer

runner = CliRunner()

PASSWORD = "abcd efgh ijkl mnop"


def _answers(*lines: str) -> str:
    return "\n".join(lines) + "\n"


# kindle, sender, host, port, security, password, "run checks now?"
NEW_CONFIG = _answers("reader@kindle.com", "me@gmail.com", "", "", "", PASSWORD, "n")


@pytest.fixture
def interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wizard, "_is_interactive", lambda: True)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_requires_an_interactive_terminal(isolated_env: Path) -> None:
    result = runner.invoke(app, ["init"], input=NEW_CONFIG)
    assert result.exit_code == 2
    assert "run it in your own terminal" in result.output
    assert not isolated_env.exists()


@pytest.mark.usefixtures("interactive")
def test_writes_private_config_that_loads(isolated_env: Path) -> None:
    result = runner.invoke(app, ["init"], input=NEW_CONFIG)
    assert result.exit_code == 0, result.output
    assert f"Saved {isolated_env} (permissions 600)" in result.output
    assert _mode(isolated_env) == 0o600
    settings = load_settings()
    assert settings.kindle_email == "reader@kindle.com"
    assert settings.sender_email == "me@gmail.com"
    assert settings.smtp_host == "smtp.gmail.com"
    assert settings.smtp_port == 587
    assert settings.smtp_security == "starttls"
    assert settings.smtp_password.get_secret_value() == PASSWORD
    assert PASSWORD not in result.output


@pytest.mark.usefixtures("interactive")
def test_creates_missing_directory_with_private_permissions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "fresh" / "s2k" / "config.env"
    monkeypatch.setenv("S2K_CONFIG_FILE", str(path))
    result = runner.invoke(app, ["init"], input=NEW_CONFIG)
    assert result.exit_code == 0, result.output
    assert _mode(path.parent) == 0o700
    assert _mode(path) == 0o600


@pytest.mark.usefixtures("interactive")
def test_invalid_email_is_asked_again(isolated_env: Path) -> None:
    answers = _answers(
        "not-an-email", "reader@kindle.com", "me@gmail.com", "", "", "", PASSWORD, "n"
    )
    result = runner.invoke(app, ["init"], input=answers)
    assert result.exit_code == 0, result.output
    assert "not a valid email address" in result.output
    assert load_settings().kindle_email == "reader@kindle.com"


@pytest.mark.usefixtures("interactive")
def test_invalid_port_is_asked_again(isolated_env: Path) -> None:
    answers = _answers(
        "reader@kindle.com", "me@gmail.com", "", "70000", "465", "ssl", PASSWORD, "n"
    )
    result = runner.invoke(app, ["init"], input=answers)
    assert result.exit_code == 0, result.output
    assert "less than or equal to 65535" in result.output
    settings = load_settings()
    assert settings.smtp_port == 465
    assert settings.smtp_security == "ssl"


@pytest.mark.usefixtures("interactive")
def test_existing_values_are_defaults_and_empty_password_keeps_it(isolated_env: Path) -> None:
    wizard.write_config(
        isolated_env,
        {
            "S2K_KINDLE_EMAIL": "old@kindle.com",
            "S2K_SENDER_EMAIL": "old@gmail.com",
            "S2K_SMTP_HOST": "smtp.example.com",
            "S2K_SMTP_PORT": "2525",
            "S2K_SMTP_SECURITY": "starttls",
            "S2K_SMTP_PASSWORD": "old secret",
            "S2K_SMTP_USERNAME": "login-user",
        },
    )
    isolated_env.chmod(0o644)
    result = runner.invoke(app, ["init"], input=_answers("", "", "", "", "", "", "n"))
    assert result.exit_code == 0, result.output
    assert "[old@kindle.com]" in result.output
    settings = load_settings()
    assert settings.kindle_email == "old@kindle.com"
    assert settings.smtp_host == "smtp.example.com"
    assert settings.smtp_port == 2525
    assert settings.smtp_password.get_secret_value() == "old secret"
    assert settings.smtp_username == "login-user"
    assert _mode(isolated_env) == 0o600


@pytest.mark.usefixtures("interactive")
def test_password_with_special_characters_round_trips(isolated_env: Path) -> None:
    password = 'p@ss "w0rd" \\ #1 $HOME ${HOME} ${S2K_X}'
    answers = _answers("reader@kindle.com", "me@gmail.com", "", "", "", password, "n")
    result = runner.invoke(app, ["init"], input=answers)
    assert result.exit_code == 0, result.output
    assert load_settings().smtp_password.get_secret_value() == password


@pytest.mark.usefixtures("interactive")
def test_abort_writes_nothing(isolated_env: Path) -> None:
    result = runner.invoke(app, ["init"], input=_answers("reader@kindle.com"))
    assert result.exit_code == 1
    assert "configuration not changed" in result.output
    assert not isolated_env.exists()


@pytest.mark.usefixtures("interactive")
def test_running_checks_uses_the_doctor_exit_code(
    isolated_env: Path, fake_smtp: FakeSMTPServer
) -> None:
    answers = _answers("reader@kindle.com", "me@gmail.com", "", "", "", PASSWORD, "y")
    result = runner.invoke(app, ["init"], input=answers)
    assert result.exit_code == 0, result.output
    assert "Logged in as me@gmail.com" in result.output
    assert result.output.rstrip().endswith("Ready.")


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root can write anywhere")
@pytest.mark.usefixtures("interactive")
def test_unwritable_config_location_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    monkeypatch.setenv("S2K_CONFIG_FILE", str(locked / "config.env"))
    locked.chmod(0o500)
    try:
        result = runner.invoke(app, ["init"], input=NEW_CONFIG)
    finally:
        locked.chmod(0o700)
    assert result.exit_code == 2
    assert "Cannot write" in result.output
    assert not (locked / "config.env").exists()
