import os
import smtplib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from send_2_kindle.main import app
from tests.fakes import FakeSMTPServer

runner = CliRunner()


def _write_config(path: Path, kindle: str = "reader@kindle.com") -> None:
    path.write_text(
        f"S2K_KINDLE_EMAIL={kindle}\nS2K_SENDER_EMAIL=me@gmail.com\nS2K_SMTP_PASSWORD=app-password\n"
    )
    path.chmod(0o600)


def test_all_checks_pass(isolated_env: Path, fake_smtp: FakeSMTPServer) -> None:
    _write_config(isolated_env)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert f"Config file: {isolated_env}" in result.output
    assert "Settings valid (sender me@gmail.com → kindle reader@kindle.com)" in result.output
    assert "Connected to smtp.gmail.com:587 (STARTTLS)" in result.output
    assert "Logged in as me@gmail.com" in result.output
    assert "Amazon cannot be checked without sending" in result.output
    assert result.output.rstrip().endswith("Ready.")
    assert not any(call.startswith("send:") for call in fake_smtp.calls)
    assert "app-password" not in result.output


def test_missing_config_points_to_init(fake_smtp: FakeSMTPServer) -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "run `s2k init` in your terminal" in result.output
    assert "SMTP login (not checked)" in result.output
    assert "Not ready: 1 problem(s)." in result.output
    assert fake_smtp.calls == []


@pytest.mark.usefixtures("valid_env")
def test_environment_only_config_is_accepted(fake_smtp: FakeSMTPServer) -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "Using environment variables" in result.output


def test_partial_environment_config_is_not_enough(
    fake_smtp: FakeSMTPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("S2K_KINDLE_EMAIL", "reader@kindle.com")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "No configuration found" in result.output


def test_permissive_file_warns_but_passes(isolated_env: Path, fake_smtp: FakeSMTPServer) -> None:
    _write_config(isolated_env)
    isolated_env.chmod(0o644)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "⚠" in result.output
    assert "chmod 600" in result.output


def test_invalid_settings_fail_without_echoing_values(
    isolated_env: Path, fake_smtp: FakeSMTPServer
) -> None:
    _write_config(isolated_env, kindle="not-an-email")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "S2K_KINDLE_EMAIL" in result.output
    assert "not-an-email" not in result.output
    assert fake_smtp.calls == []


def test_connection_failure_skips_login(isolated_env: Path, fake_smtp: FakeSMTPServer) -> None:
    _write_config(isolated_env)
    fake_smtp.connect_error = ConnectionRefusedError("refused")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "could not connect to smtp.gmail.com:587" in result.output
    assert "SMTP login (not checked)" in result.output


def test_auth_failure_reports_connection_ok(isolated_env: Path, fake_smtp: FakeSMTPServer) -> None:
    _write_config(isolated_env)
    fake_smtp.login_error = smtplib.SMTPAuthenticationError(535, b"bad credentials")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "Connected to smtp.gmail.com:587 (STARTTLS)" in result.output
    assert "app password" in result.output
    assert "app-password" not in result.output


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root can read any file")
def test_unreadable_config_file_is_reported(isolated_env: Path, fake_smtp: FakeSMTPServer) -> None:
    _write_config(isolated_env)
    isolated_env.chmod(0)
    try:
        result = runner.invoke(app, ["doctor"])
    finally:
        isolated_env.chmod(0o600)
    assert result.exit_code == 1
    assert "Cannot read" in result.output
    assert fake_smtp.calls == []
