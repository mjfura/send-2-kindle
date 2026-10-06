"""Build Send to Kindle emails and send them over one SMTP session."""

import mimetypes
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from types import TracebackType
from typing import Self

from send_2_kindle import constants
from send_2_kindle.config import Settings
from send_2_kindle.errors import SendError, SmtpAuthError, SmtpConnectionError


def build_message(settings: Settings, path: Path) -> EmailMessage:
    """Return an email to the Kindle address with ``path`` as its only attachment."""
    message = EmailMessage()
    message["From"] = settings.sender_email
    message["To"] = settings.kindle_email
    message["Subject"] = path.name
    message.set_content("")

    mime_type, _ = mimetypes.guess_type(path.name)
    maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
    message.add_attachment(
        path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name
    )
    return message


def _text(value: bytes | str) -> str:
    return value.decode(errors="replace") if isinstance(value, bytes) else value


def _auth_failure_message(settings: Settings) -> str:
    message = f"authentication failed for {settings.login_username} on {settings.smtp_host}"
    if settings.smtp_host == constants.GMAIL_SMTP_HOST:
        message += (
            ". Gmail requires an app password, not your account password: "
            f"{constants.GMAIL_APP_PASSWORDS_URL}"
        )
    return message


def _security_hint(settings: Settings) -> str:
    if settings.smtp_port == 465 and settings.smtp_security == "starttls":
        return " (port 465 normally needs S2K_SMTP_SECURITY=ssl)"
    if settings.smtp_port == 587 and settings.smtp_security == "ssl":
        return " (port 587 normally needs S2K_SMTP_SECURITY=starttls)"
    return ""


def _close_quietly(smtp: smtplib.SMTP | None) -> None:
    if smtp is not None:
        smtp.close()


def _login(smtp: smtplib.SMTP, settings: Settings) -> None:
    """Log in, reporting any other SMTP refusal of the login as an auth error."""
    try:
        smtp.login(settings.login_username, settings.smtp_password.get_secret_value())
    except (
        smtplib.SMTPAuthenticationError,
        smtplib.SMTPNotSupportedError,
        smtplib.SMTPServerDisconnected,
    ):
        raise
    except smtplib.SMTPException as error:
        _close_quietly(smtp)
        raise SmtpAuthError(
            f"login failed for {settings.login_username} on {settings.smtp_host}: {error}"
        ) from error


class KindleMailer:
    """One authenticated SMTP session that sends one email per file.

    Use as a context manager: ``with KindleMailer(settings) as mailer: mailer.send(path)``.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._smtp: smtplib.SMTP | None = None

    def __enter__(self) -> Self:
        settings = self._settings
        smtp: smtplib.SMTP | None = None
        try:
            if settings.smtp_security == "ssl":
                smtp = smtplib.SMTP_SSL(
                    settings.smtp_host,
                    settings.smtp_port,
                    timeout=constants.SMTP_TIMEOUT_SECONDS,
                    context=ssl.create_default_context(),
                )
            else:
                smtp = smtplib.SMTP(
                    settings.smtp_host,
                    settings.smtp_port,
                    timeout=constants.SMTP_TIMEOUT_SECONDS,
                )
                smtp.starttls(context=ssl.create_default_context())
            _login(smtp, settings)
        except smtplib.SMTPAuthenticationError as error:
            _close_quietly(smtp)
            raise SmtpAuthError(_auth_failure_message(settings)) from error
        except UnicodeEncodeError as error:  # smtplib sends credentials as ASCII
            _close_quietly(smtp)
            raise SmtpAuthError(
                "SMTP username and password must contain only ASCII characters"
            ) from error
        except smtplib.SMTPNotSupportedError as error:  # e.g. no STARTTLS or no AUTH
            _close_quietly(smtp)
            raise SmtpConnectionError(
                f"{settings.smtp_host}:{settings.smtp_port} does not support a required feature "
                f"(check S2K_SMTP_SECURITY and S2K_SMTP_PORT): {error}"
            ) from error
        except OSError as error:  # smtplib.SMTPException, timeouts and ssl.SSLError are OSErrors
            _close_quietly(smtp)
            raise SmtpConnectionError(
                f"could not connect to {settings.smtp_host}:{settings.smtp_port}: {error}"
                f"{_security_hint(settings)}"
            ) from error
        self._smtp = smtp
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        smtp, self._smtp = self._smtp, None
        if smtp is None:
            return
        try:
            smtp.quit()
        except OSError:
            smtp.close()

    def send(self, path: Path) -> None:
        """Send ``path`` as one email.

        Raises SendError when only this message failed, and SmtpConnectionError when the
        session is lost.
        """
        if self._smtp is None:
            raise RuntimeError("KindleMailer.send() must be called inside a 'with' block")
        try:
            message = build_message(self._settings, path)
        except OSError as error:
            raise SendError(f"could not read file: {error}") from error
        try:
            self._smtp.send_message(message)
        except smtplib.SMTPServerDisconnected as error:
            raise SmtpConnectionError(f"connection lost: {error}") from error
        except smtplib.SMTPRecipientsRefused as error:
            details = "; ".join(
                f"{address}: {code} {_text(reply)}"
                for address, (code, reply) in error.recipients.items()
            )
            raise SendError(f"recipient refused: {details}") from error
        except smtplib.SMTPResponseException as error:
            raise SendError(
                f"server rejected the message: {error.smtp_code} {_text(error.smtp_error)}"
            ) from error
        except smtplib.SMTPException as error:
            raise SendError(f"server rejected the message: {error}") from error
        except OSError as error:  # network errors and timeouts after login
            raise SmtpConnectionError(f"connection lost: {error}") from error
