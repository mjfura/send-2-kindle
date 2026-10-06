"""Configuration loaded from S2K_* environment variables and cli/.env."""

from pathlib import Path
from typing import Final, Literal

from pydantic import EmailStr, Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from send_2_kindle import constants
from send_2_kindle.errors import ConfigError

# cli/src/send_2_kindle/config.py -> parents[2] is cli/
PROJECT_DIR: Final[Path] = Path(__file__).resolve().parents[2]
ENV_FILE: Path = PROJECT_DIR / ".env"

ENV_PREFIX: Final[str] = "S2K_"


class Settings(BaseSettings):
    """Validated s2k configuration. Real environment variables override the .env file."""

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX, env_file_encoding="utf-8", extra="ignore"
    )

    kindle_email: EmailStr
    sender_email: EmailStr
    smtp_password: SecretStr
    smtp_host: str = Field(default=constants.GMAIL_SMTP_HOST, min_length=1)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_security: Literal["starttls", "ssl"] = "starttls"
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


def _describe(error: ValidationError) -> str:
    lines = ["Invalid configuration (check cli/.env or your environment variables):"]
    for item in error.errors():
        field = str(item["loc"][0]) if item["loc"] else "?"
        reason = "is required" if item["type"] == "missing" else item["msg"]
        lines.append(f"  {ENV_PREFIX}{field.upper()}: {reason}")
    return "\n".join(lines)


def load_settings() -> Settings:
    """Load settings from the environment and ENV_FILE, raising ConfigError if invalid."""
    try:
        return Settings(_env_file=ENV_FILE)
    except ValidationError as error:
        raise ConfigError(_describe(error)) from None
