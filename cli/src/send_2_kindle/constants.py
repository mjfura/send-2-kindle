"""Fixed values: Amazon Send to Kindle limits and SMTP defaults."""

from typing import Final

# Formats accepted by Send to Kindle by email (verified 2026-10-05). MOBI is no longer accepted.
ALLOWED_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".doc", ".docx", ".html", ".htm", ".rtf", ".txt",
        ".jpeg", ".jpg", ".gif", ".png", ".bmp", ".pdf", ".epub",
    }
)  # fmt: skip

# Amazon allows 50 MB per email; decimal megabytes is the conservative reading.
MAX_EMAIL_SIZE_BYTES: Final[int] = 50_000_000

SMTP_TIMEOUT_SECONDS: Final[float] = 30.0

GMAIL_SMTP_HOST: Final[str] = "smtp.gmail.com"
GMAIL_APP_PASSWORDS_URL: Final[str] = "https://myaccount.google.com/apppasswords"
