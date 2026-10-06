"""Configuration loaded from S2K_* environment variables and the user's config file."""

import os
from pathlib import Path
from typing import Annotated, Final, Literal

from pydantic import EmailStr, Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from send_2_kindle import constants
from send_2_kindle.errors import ConfigError

ENV_PREFIX: Final[str] = "S2K_"
CONFIG_FILE_VARIABLE: Final[str] = "S2K_CONFIG_FILE"
REQUIRED_VARIABLES: Final[tuple[str, ...]] = (
    "S2K_KINDLE_EMAIL",
    "S2K_SENDER_EMAIL",
    "S2K_SMTP_PASSWORD",
)

# Field types shared by Settings and the `s2k init` wizard, so both validate the same way.
SmtpHost = Annotated[str, Field(min_length=1)]
SmtpPort = Annotated[int, Field(ge=1, le=65535)]
SmtpSecurity = Literal["starttls", "ssl"]


def config_file_path() -> Path:
    """Return the config file s2k reads (it may not exist).

    $S2K_CONFIG_FILE, else $XDG_CONFIG_HOME/s2k/config.env, else ~/.config/s2k/config.env.
    """
    override = os.environ.get(CONFIG_FILE_VARIABLE)
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or "~/.config"
    return Path(base).expanduser() / "s2k" / "config.env"


class Settings(BaseSettings):
    """Validated s2k configuration. Real environment variables override the config file."""

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX, env_file_encoding="utf-8", extra="ignore"
    )

    kindle_email: EmailStr
    sender_email: EmailStr
    smtp_password: SecretStr
    smtp_host: SmtpHost = constants.GMAIL_SMTP_HOST
    smtp_port: SmtpPort = 587
    smtp_security: SmtpSecurity = "starttls"
    smtp_username: str | None = None

    @field_validator("smtp_password")
    @classmethod
    def _password_not_empty(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value():
            raise ValueError("must not be empty")
        return value

    @property
    def login_username(self) -> str:
        """SMTP login: S2K_SMTP_USERNAME, or the sender address when unset or empty."""
        return self.smtp_username or self.sender_email


def _describe(error: ValidationError, path: Path) -> str:
    lines = [f"Invalid configuration (check {path} or your environment variables):"]
    for item in error.errors():
        field = str(item["loc"][0]) if item["loc"] else "?"
        reason = "is required" if item["type"] == "missing" else item["msg"]
        lines.append(f"  {ENV_PREFIX}{field.upper()}: {reason}")
    return "\n".join(lines)


def load_settings() -> Settings:
    """Load settings from the environment and config_file_path(), raising ConfigError if invalid."""
    path = config_file_path()
    try:
        return Settings(_env_file=path)
    except ValidationError as error:
        raise ConfigError(_describe(error, path)) from None
    except OSError as error:
        raise ConfigError(f"Cannot read {path}: {error.strerror or error}") from None
