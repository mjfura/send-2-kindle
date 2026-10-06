"""Known email providers: SMTP settings, attachment limits and where to get their passwords."""

from dataclasses import dataclass, field
from typing import Final


@dataclass(frozen=True)
class Provider:
    key: str
    name: str
    host: str
    port: int
    security: str
    # Message limits (Gmail 25 MB, iCloud 20 MB) divided by ~1.37 (base64 4/3 and CRLF line
    # wrapping 78/76), rounded down: 18 MB → ~24.6 MB, 14 MB → ~19.2 MB.
    max_file_bytes: int
    password_name: str
    password_url: str
    aliases: tuple[str, ...] = field(default=())


GMAIL: Final = Provider(
    "gmail", "Gmail", "smtp.gmail.com", 587, "starttls", 18_000_000,
    "app password", "https://myaccount.google.com/apppasswords",
)  # fmt: skip
ICLOUD: Final = Provider(
    "icloud", "iCloud", "smtp.mail.me.com", 587, "starttls", 14_000_000,
    "app-specific password", "https://account.apple.com", ("smtp.me.com", "smtp.mac.com"),
)  # fmt: skip
PROVIDERS: Final[tuple[Provider, ...]] = (GMAIL, ICLOUD)


def provider_for_host(host: str) -> Provider | None:
    """Return the provider whose SMTP server is ``host`` (case and spaces ignored)."""
    normalized = host.strip().lower()
    return next((p for p in PROVIDERS if normalized == p.host or normalized in p.aliases), None)


def provider_for_key(key: str) -> Provider | None:
    return next((provider for provider in PROVIDERS if provider.key == key), None)
