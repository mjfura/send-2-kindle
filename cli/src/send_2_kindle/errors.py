"""Exceptions raised by s2k. Messages are shown to the user as-is."""


class S2KError(Exception):
    """Base class for every expected s2k error."""


class ConfigError(S2KError):
    """The configuration (.env or environment variables) is missing or invalid."""


class FileValidationError(S2KError):
    """A file cannot be sent (missing, unsupported, empty, unreadable or too large)."""


class SmtpConnectionError(S2KError):
    """The SMTP server cannot be reached or the connection was lost."""


class SmtpAuthError(S2KError):
    """The SMTP server rejected the credentials."""


class SendError(S2KError):
    """The SMTP server rejected one specific message."""
