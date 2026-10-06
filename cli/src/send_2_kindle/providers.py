"""Known email providers: SMTP settings, attachment limits and where to get their passwords."""

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Provider:
    key: str
    name: str
    host: str
    port: int
    security: str
    # Message limits (Gmail 25 MB, iCloud 20 MB) minus ~33 % base64 growth, rounded down.
    max_file_bytes: int
    password_name: str
    password_url: str


GMAIL: Final = Provider(
    "gmail", "Gmail", "smtp.gmail.com", 587, "starttls", 18_000_000,
    "app password", "https://myaccount.google.com/apppasswords",
)  # fmt: skip
ICLOUD: Final = Provider(
    "icloud", "iCloud", "smtp.mail.me.com", 587, "starttls", 14_000_000,
    "app-specific password", "https://account.apple.com",
)  # fmt: skip
PROVIDERS: Final[tuple[Provider, ...]] = (GMAIL, ICLOUD)


def provider_for_host(host: str) -> Provider | None:
    """Return the provider whose SMTP server is ``host`` (case and spaces ignored)."""
    normalized = host.strip().lower()
    return next((provider for provider in PROVIDERS if provider.host == normalized), None)


def provider_for_key(key: str) -> Provider | None:
    return next((provider for provider in PROVIDERS if provider.key == key), None)
