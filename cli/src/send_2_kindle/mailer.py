"""Build Send to Kindle emails and send them over one SMTP session."""

import mimetypes
from email.message import EmailMessage
from pathlib import Path

from send_2_kindle.config import Settings


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
