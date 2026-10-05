import mimetypes
from pathlib import Path

import pytest

from send_2_kindle.config import Settings
from send_2_kindle.mailer import build_message


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
