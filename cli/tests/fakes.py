"""In-memory stand-in for smtplib so tests never touch the network."""

import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage

import pytest


@dataclass
class FakeSMTPServer:
    connect_error: OSError | None = None
    login_error: OSError | None = None
    send_errors: dict[str, OSError] = field(default_factory=dict)  # keyed by Subject
    calls: list[str] = field(default_factory=list)
    sent: list[EmailMessage] = field(default_factory=list)

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        server = self

        class FakeSMTP:
            kind = "smtp"

            def __init__(
                self, host: str, port: int, timeout: float = 0.0, context: object = None
            ) -> None:
                server.calls.append(f"connect:{self.kind}:{host}:{port}:{timeout}")
                if server.connect_error is not None:
                    raise server.connect_error

            def starttls(self, context: object = None) -> None:
                server.calls.append("starttls")

            def login(self, user: str, password: str) -> None:
                server.calls.append(f"login:{user}:{password}")
                if server.login_error is not None:
                    raise server.login_error

            def send_message(self, message: EmailMessage) -> None:
                subject = str(message["Subject"])
                server.calls.append(f"send:{subject}")
                error = server.send_errors.get(subject)
                if error is not None:
                    raise error
                server.sent.append(message)

            def quit(self) -> None:
                server.calls.append("quit")

            def close(self) -> None:
                server.calls.append("close")

        class FakeSMTPSSL(FakeSMTP):
            kind = "ssl"

        monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
        monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTPSSL)
