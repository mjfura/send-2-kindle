"""Shared fixtures. Tests never read the real cli/.env or S2K_* shell variables."""

import os
from pathlib import Path

import pytest

from send_2_kindle import config
from send_2_kindle.config import Settings


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    for name in list(os.environ):
        if name.startswith("S2K_"):
            monkeypatch.delenv(name)
    env_file = tmp_path / "test.env"
    monkeypatch.setattr(config, "ENV_FILE", env_file)
    return env_file


@pytest.fixture
def valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("S2K_KINDLE_EMAIL", "reader@kindle.com")
    monkeypatch.setenv("S2K_SENDER_EMAIL", "me@gmail.com")
    monkeypatch.setenv("S2K_SMTP_PASSWORD", "app-password")


@pytest.fixture
def settings(valid_env: None) -> Settings:
    return config.load_settings()
