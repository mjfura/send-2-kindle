import os
from pathlib import Path

import pytest

from send_2_kindle import constants
from send_2_kindle.errors import FileValidationError
from send_2_kindle.validation import validate_file


def _file(directory: Path, name: str, content: bytes = b"data") -> Path:
    path = directory / name
    path.write_bytes(content)
    return path


@pytest.mark.parametrize("extension", sorted(constants.ALLOWED_EXTENSIONS))
def test_accepts_every_allowed_extension(tmp_path: Path, extension: str) -> None:
    validate_file(_file(tmp_path, f"document{extension}"))


def test_extension_check_is_case_insensitive(tmp_path: Path) -> None:
    validate_file(_file(tmp_path, "BOOK.EPUB"))


@pytest.mark.parametrize("name", ["book.mobi", "archive.zip", "README"])
def test_rejects_unsupported_extension(tmp_path: Path, name: str) -> None:
    with pytest.raises(FileValidationError, match="unsupported extension"):
        validate_file(_file(tmp_path, name))


def test_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileValidationError, match="file not found"):
        validate_file(tmp_path / "missing.pdf")


def test_rejects_directory(tmp_path: Path) -> None:
    directory = tmp_path / "folder.pdf"
    directory.mkdir()
    with pytest.raises(FileValidationError, match="not a regular file"):
        validate_file(directory)


def test_rejects_empty_file(tmp_path: Path) -> None:
    with pytest.raises(FileValidationError, match="file is empty"):
        validate_file(_file(tmp_path, "empty.txt", b""))


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root can read any file")
def test_rejects_unreadable_file(tmp_path: Path) -> None:
    path = _file(tmp_path, "secret.txt")
    path.chmod(0)
    try:
        with pytest.raises(FileValidationError, match="file is not readable"):
            validate_file(path)
    finally:
        path.chmod(0o600)


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root can read any file")
def test_file_in_inaccessible_directory_is_not_readable(tmp_path: Path) -> None:
    # Path.exists() is False here, but the file exists: "file not found" would mislead.
    directory = tmp_path / "locked"
    directory.mkdir()
    path = _file(directory, "book.pdf")
    directory.chmod(0)
    try:
        with pytest.raises(FileValidationError, match="file is not readable"):
            validate_file(path)
    finally:
        directory.chmod(0o700)


def test_accepts_file_exactly_at_size_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(constants, "MAX_EMAIL_SIZE_BYTES", 10)
    validate_file(_file(tmp_path, "limit.txt", b"x" * 10))


def test_rejects_file_over_size_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(constants, "MAX_EMAIL_SIZE_BYTES", 10)
    with pytest.raises(FileValidationError, match="file exceeds"):
        validate_file(_file(tmp_path, "big.txt", b"x" * 11))
