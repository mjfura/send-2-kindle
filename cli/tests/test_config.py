import os
from pathlib import Path

import pytest

from send_2_kindle import config
from send_2_kindle.config import load_settings
from send_2_kindle.errors import ConfigError

REQUIRED_FILE_LINES = "S2K_KINDLE_EMAIL=reader@kindle.com\nS2K_SENDER_EMAIL=me@gmail.com\n"


@pytest.mark.usefixtures("valid_env")
def test_loads_required_values_and_defaults() -> None:
    settings = load_settings()
    assert settings.kindle_email == "reader@kindle.com"
    assert settings.sender_email == "me@gmail.com"
    assert settings.smtp_password.get_secret_value() == "app-password"
    assert settings.smtp_host == "smtp.gmail.com"
    assert settings.smtp_port == 587
    assert settings.smtp_security == "starttls"
    assert settings.smtp_username is None


@pytest.mark.usefixtures("valid_env")
def test_login_username_falls_back_to_sender() -> None:
    assert load_settings().login_username == "me@gmail.com"


@pytest.mark.usefixtures("valid_env")
def test_empty_username_falls_back_to_sender(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("S2K_SMTP_USERNAME", "")
    assert load_settings().login_username == "me@gmail.com"


@pytest.mark.usefixtures("valid_env")
def test_explicit_username_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("S2K_SMTP_USERNAME", "login-user")
    assert load_settings().login_username == "login-user"


def test_missing_required_variables_are_listed() -> None:
    with pytest.raises(ConfigError) as exc_info:
        load_settings()
    message = str(exc_info.value)
    for name in ("S2K_KINDLE_EMAIL", "S2K_SENDER_EMAIL", "S2K_SMTP_PASSWORD"):
        assert name in message
    assert "is required" in message


@pytest.mark.usefixtures("valid_env")
def test_invalid_values_are_reported_without_echoing_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("S2K_KINDLE_EMAIL", "not-an-email")
    monkeypatch.setenv("S2K_SMTP_PORT", "70000")
    monkeypatch.setenv("S2K_SMTP_SECURITY", "tls")
    with pytest.raises(ConfigError) as exc_info:
        load_settings()
    message = str(exc_info.value)
    for name in ("S2K_KINDLE_EMAIL", "S2K_SMTP_PORT", "S2K_SMTP_SECURITY"):
        assert name in message
    assert "not-an-email" not in message


@pytest.mark.usefixtures("valid_env")
def test_empty_password_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("S2K_SMTP_PASSWORD", "")
    with pytest.raises(ConfigError, match="S2K_SMTP_PASSWORD"):
        load_settings()


def test_reads_values_from_env_file(isolated_env: Path) -> None:
    # Gmail shows app passwords as four space-separated groups; keep them intact.
    isolated_env.write_text(REQUIRED_FILE_LINES + "S2K_SMTP_PASSWORD=abcd efgh ijkl mnop\n")
    settings = load_settings()
    assert settings.kindle_email == "reader@kindle.com"
    assert settings.smtp_password.get_secret_value() == "abcd efgh ijkl mnop"


def test_environment_variables_override_env_file(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolated_env.write_text(REQUIRED_FILE_LINES + "S2K_SMTP_PASSWORD=secret\n")
    monkeypatch.setenv("S2K_KINDLE_EMAIL", "other@kindle.com")
    assert load_settings().kindle_email == "other@kindle.com"


def test_unrelated_variables_in_env_file_are_ignored(isolated_env: Path) -> None:
    isolated_env.write_text(REQUIRED_FILE_LINES + "S2K_SMTP_PASSWORD=secret\nOTHER_TOOL=1\n")
    assert load_settings().smtp_password.get_secret_value() == "secret"


@pytest.mark.usefixtures("valid_env")
def test_password_is_masked_in_repr() -> None:
    assert "app-password" not in repr(load_settings())


def test_config_file_variable_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("S2K_CONFIG_FILE", str(tmp_path / "custom.env"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert config.config_file_path() == tmp_path / "custom.env"


def test_config_file_variable_expands_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("S2K_CONFIG_FILE", "~/s2k.env")
    assert config.config_file_path() == tmp_path / "home" / "s2k.env"


def test_xdg_config_home_is_used(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("S2K_CONFIG_FILE")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert config.config_file_path() == tmp_path / "xdg" / "s2k" / "config.env"


def test_default_is_dot_config_in_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("S2K_CONFIG_FILE")
    assert config.config_file_path() == tmp_path / "home" / ".config" / "s2k" / "config.env"


def test_empty_xdg_config_home_falls_back_to_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("S2K_CONFIG_FILE")
    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    assert config.config_file_path() == tmp_path / "home" / ".config" / "s2k" / "config.env"


def test_load_settings_reads_the_resolved_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("S2K_CONFIG_FILE")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    path = tmp_path / "xdg" / "s2k" / "config.env"
    path.parent.mkdir(parents=True)
    path.write_text(REQUIRED_FILE_LINES + "S2K_SMTP_PASSWORD=secret\n")
    assert load_settings().smtp_password.get_secret_value() == "secret"


def test_dot_env_in_working_directory_is_ignored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workdir = tmp_path / "project"
    workdir.mkdir()
    (workdir / ".env").write_text(REQUIRED_FILE_LINES + "S2K_SMTP_PASSWORD=secret\n")
    monkeypatch.chdir(workdir)
    with pytest.raises(ConfigError):
        load_settings()


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root can read any file")
def test_unreadable_config_file_is_a_config_error(isolated_env: Path) -> None:
    isolated_env.write_text(REQUIRED_FILE_LINES + "S2K_SMTP_PASSWORD=secret\n")
    isolated_env.chmod(0)
    try:
        with pytest.raises(ConfigError, match="Cannot read"):
            load_settings()
    finally:
        isolated_env.chmod(0o600)


def test_config_file_values_are_read_literally(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # python-dotenv would expand ${FOO}; a password must come back exactly as written.
    monkeypatch.setenv("FOO", "EXPANDED")
    isolated_env.write_text(REQUIRED_FILE_LINES + 'S2K_SMTP_PASSWORD="a${FOO}b${HOME}c"\n')
    assert load_settings().smtp_password.get_secret_value() == "a${FOO}b${HOME}c"
