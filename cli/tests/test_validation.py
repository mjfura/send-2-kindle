import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from send_2_kindle import constants, validation
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


def test_size_limit_names_the_provider(tmp_path: Path) -> None:
    with pytest.raises(FileValidationError, match=r"file exceeds 1e-05 MB, the limit for iCloud"):
        validate_file(_file(tmp_path, "big.pdf", b"x" * 11), max_bytes=10, provider_name="iCloud")


class _StatPath(type(Path())):  # type: ignore[misc]
    """A Path whose stat() returns a fixed result, so no global patching is needed."""

    stat_result: object = SimpleNamespace()

    def stat(self, *, follow_symlinks: bool = True) -> object:
        return self.stat_result


def _stat_path(**fields: int) -> Path:
    path = _StatPath("cloud.pdf")
    path.stat_result = SimpleNamespace(**fields)
    return path


def test_is_not_downloaded_reads_the_dataless_flag() -> None:
    assert validation.is_not_downloaded(_stat_path(st_flags=validation.SF_DATALESS))
    assert not validation.is_not_downloaded(_stat_path(st_flags=0))


def test_is_not_downloaded_without_st_flags() -> None:
    assert not validation.is_not_downloaded(_stat_path())


def test_is_not_downloaded_on_missing_file(tmp_path: Path) -> None:
    assert not validation.is_not_downloaded(tmp_path / "missing.pdf")
