import mimetypes
import smtplib
from pathlib import Path

import pytest

from send_2_kindle.config import Settings, load_settings
from send_2_kindle.errors import SendError, SmtpAuthError, SmtpConnectionError
from send_2_kindle.mailer import KindleMailer, build_message
from tests.fakes import FakeSMTPServer


def _file(directory: Path, name: str, content: bytes = b"data") -> Path:
    path = directory / name
    path.write_bytes(content)
    return path


def test_build_message_headers(settings: Settings, tmp_path: Path) -> None:
    message = build_message(settings, _file(tmp_path, "book.pdf"))
    assert message["From"] == "me@gmail.com"
    assert message["To"] == "reader@kindle.com"
    assert message["Subject"] == "book.pdf"


def test_build_message_has_single_attachment_with_file_bytes(
    settings: Settings, tmp_path: Path
) -> None:
    message = build_message(settings, _file(tmp_path, "book.pdf", b"%PDF-1.7 fake"))
    attachments = list(message.iter_attachments())
    assert len(attachments) == 1
    attachment = attachments[0]
    assert attachment.get_filename() == "book.pdf"
    assert attachment.get_content_type() == "application/pdf"
    assert attachment.get_payload(decode=True) == b"%PDF-1.7 fake"


@pytest.mark.parametrize("name", ["notes.txt", "page.html", "photo.jpg", "book.epub"])
def test_build_message_attaches_any_allowed_type(
    settings: Settings, tmp_path: Path, name: str
) -> None:
    message = build_message(settings, _file(tmp_path, name, b"content"))
    attachment = next(iter(message.iter_attachments()))
    assert attachment.get_filename() == name
    assert attachment.get_payload(decode=True) == b"content"


def test_build_message_falls_back_to_octet_stream(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mimetypes, "guess_type", lambda *args, **kwargs: (None, None))
    message = build_message(settings, _file(tmp_path, "book.epub"))
    attachment = next(iter(message.iter_attachments()))
    assert attachment.get_content_type() == "application/octet-stream"


def test_build_message_keeps_non_ascii_file_name(settings: Settings, tmp_path: Path) -> None:
    name = "Cien años de soledad.epub"
    message = build_message(settings, _file(tmp_path, name))
    assert message["Subject"] == name
    attachment = next(iter(message.iter_attachments()))
    assert attachment.get_filename() == name
    assert message.as_bytes()  # serializes without UnicodeEncodeError


def test_starttls_session_sends_and_quits(
    settings: Settings, fake_smtp: FakeSMTPServer, tmp_path: Path
) -> None:
    with KindleMailer(settings) as mailer:
        mailer.send(_file(tmp_path, "book.pdf"))
    assert fake_smtp.calls == [
        "connect:smtp:smtp.gmail.com:587:30.0",
        "starttls",
        "login:me@gmail.com:app-password",
        "send:book.pdf",
        "quit",
    ]
    assert [str(m["Subject"]) for m in fake_smtp.sent] == ["book.pdf"]


@pytest.mark.usefixtures("valid_env")
def test_ssl_session_skips_starttls(
    fake_smtp: FakeSMTPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("S2K_SMTP_SECURITY", "ssl")
    monkeypatch.setenv("S2K_SMTP_PORT", "465")
    with KindleMailer(load_settings()):
        pass
    assert fake_smtp.calls[0] == "connect:ssl:smtp.gmail.com:465:30.0"
    assert "starttls" not in fake_smtp.calls


def test_connection_failure_raises_connection_error(
    settings: Settings, fake_smtp: FakeSMTPServer
) -> None:
    fake_smtp.connect_error = ConnectionRefusedError("refused")
    with pytest.raises(SmtpConnectionError, match=r"smtp\.gmail\.com:587"), KindleMailer(settings):
        pass


def test_gmail_auth_failure_mentions_app_password(
    settings: Settings, fake_smtp: FakeSMTPServer
) -> None:
    fake_smtp.login_error = smtplib.SMTPAuthenticationError(535, b"bad credentials")
    with pytest.raises(SmtpAuthError, match="app password"), KindleMailer(settings):
        pass
    assert "close" in fake_smtp.calls


@pytest.mark.usefixtures("valid_env")
def test_other_provider_auth_failure_has_no_gmail_hint(
    fake_smtp: FakeSMTPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("S2K_SMTP_HOST", "smtp.example.com")
    fake_smtp.login_error = smtplib.SMTPAuthenticationError(535, b"bad credentials")
    with pytest.raises(SmtpAuthError) as exc_info, KindleMailer(load_settings()):
        pass
    assert "app password" not in str(exc_info.value)


def test_recipient_refused_is_a_send_error(
    settings: Settings, fake_smtp: FakeSMTPServer, tmp_path: Path
) -> None:
    fake_smtp.send_errors["book.pdf"] = smtplib.SMTPRecipientsRefused(
        {"reader@kindle.com": (550, b"no such user")}
    )
    with KindleMailer(settings) as mailer, pytest.raises(SendError, match="550 no such user"):
        mailer.send(_file(tmp_path, "book.pdf"))


def test_rejected_message_is_a_send_error(
    settings: Settings, fake_smtp: FakeSMTPServer, tmp_path: Path
) -> None:
    fake_smtp.send_errors["book.pdf"] = smtplib.SMTPDataError(552, b"message too large")
    with KindleMailer(settings) as mailer, pytest.raises(SendError, match="552 message too large"):
        mailer.send(_file(tmp_path, "book.pdf"))


def test_disconnect_during_send_is_a_connection_error(
    settings: Settings, fake_smtp: FakeSMTPServer, tmp_path: Path
) -> None:
    fake_smtp.send_errors["book.pdf"] = smtplib.SMTPServerDisconnected("gone")
    with KindleMailer(settings) as mailer, pytest.raises(SmtpConnectionError):
        mailer.send(_file(tmp_path, "book.pdf"))


def test_send_timeout_is_a_connection_error(
    settings: Settings, fake_smtp: FakeSMTPServer, tmp_path: Path
) -> None:
    fake_smtp.send_errors["book.pdf"] = TimeoutError("timed out")
    with KindleMailer(settings) as mailer, pytest.raises(SmtpConnectionError):
        mailer.send(_file(tmp_path, "book.pdf"))


@pytest.mark.usefixtures("fake_smtp")
def test_unreadable_file_at_send_time_is_a_send_error(settings: Settings, tmp_path: Path) -> None:
    with KindleMailer(settings) as mailer, pytest.raises(SendError, match="could not read"):
        mailer.send(tmp_path / "deleted-after-validation.pdf")


def test_send_outside_context_manager_is_a_programming_error(
    settings: Settings, tmp_path: Path
) -> None:
    with pytest.raises(RuntimeError):
        KindleMailer(settings).send(_file(tmp_path, "book.pdf"))


def test_non_ascii_credentials_are_an_auth_error(
    settings: Settings, fake_smtp: FakeSMTPServer
) -> None:
    # smtplib encodes credentials as ASCII; a password like "contraseña" must not crash.
    fake_smtp.login_error = UnicodeEncodeError("ascii", "contraseña", 8, 9, "not ASCII")
    with pytest.raises(SmtpAuthError, match="ASCII"), KindleMailer(settings):
        pass
    assert "close" in fake_smtp.calls


def test_server_without_required_feature_is_reported_as_such(
    settings: Settings, fake_smtp: FakeSMTPServer
) -> None:
    fake_smtp.login_error = smtplib.SMTPNotSupportedError("SMTP AUTH extension not supported")
    with pytest.raises(SmtpConnectionError, match="does not support"), KindleMailer(settings):
        pass
    assert "close" in fake_smtp.calls


def test_other_login_failures_are_auth_errors(
    settings: Settings, fake_smtp: FakeSMTPServer
) -> None:
    fake_smtp.login_error = smtplib.SMTPException("No suitable authentication method found.")
    with pytest.raises(SmtpAuthError, match="login failed"), KindleMailer(settings):
        pass
    assert "close" in fake_smtp.calls


@pytest.mark.usefixtures("valid_env")
def test_starttls_on_port_465_gets_a_hint(
    fake_smtp: FakeSMTPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("S2K_SMTP_PORT", "465")
    fake_smtp.connect_error = TimeoutError("timed out")
    with (
        pytest.raises(SmtpConnectionError, match="S2K_SMTP_SECURITY=ssl"),
        KindleMailer(load_settings()),
    ):
        pass


@pytest.mark.usefixtures("valid_env")
def test_ssl_on_port_587_gets_a_hint(
    fake_smtp: FakeSMTPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("S2K_SMTP_SECURITY", "ssl")
    fake_smtp.connect_error = ConnectionResetError("reset")
    with (
        pytest.raises(SmtpConnectionError, match="S2K_SMTP_SECURITY=starttls"),
        KindleMailer(load_settings()),
    ):
        pass


@pytest.mark.usefixtures("valid_env")
def test_icloud_auth_failure_mentions_app_specific_password(
    fake_smtp: FakeSMTPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("S2K_SMTP_HOST", "smtp.mail.me.com")
    fake_smtp.login_error = smtplib.SMTPAuthenticationError(535, b"bad credentials")
    with (
        pytest.raises(SmtpAuthError, match=r"app-specific password.*account\.apple\.com"),
        KindleMailer(load_settings()),
    ):
        pass
