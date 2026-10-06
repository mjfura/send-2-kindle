"""Shared fixtures. Tests never read the real user config or S2K_* shell variables."""

import os
from pathlib import Path

import pytest

from send_2_kindle import config
from send_2_kindle.config import Settings
from tests.fakes import FakeSMTPServer


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    for name in list(os.environ):
        if name.startswith("S2K_"):
            monkeypatch.delenv(name)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    config_file = tmp_path / "config.env"
    monkeypatch.setenv("S2K_CONFIG_FILE", str(config_file))
    return config_file


@pytest.fixture
def valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("S2K_KINDLE_EMAIL", "reader@kindle.com")
    monkeypatch.setenv("S2K_SENDER_EMAIL", "me@gmail.com")
    monkeypatch.setenv("S2K_SMTP_PASSWORD", "app-password")


@pytest.fixture
def settings(valid_env: None) -> Settings:
    return config.load_settings()


@pytest.fixture
def fake_smtp(monkeypatch: pytest.MonkeyPatch) -> FakeSMTPServer:
    server = FakeSMTPServer()
    server.install(monkeypatch)
    return server
