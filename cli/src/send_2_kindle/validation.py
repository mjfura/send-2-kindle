"""Local checks that decide whether a file can be sent to Kindle."""

import os
from pathlib import Path

from send_2_kindle import constants
from send_2_kindle.errors import FileValidationError


def _megabytes(size: int) -> float:
    return size / 1_000_000


def validate_file(path: Path) -> None:
    """Raise FileValidationError with a user-facing reason if ``path`` cannot be sent."""
    if not path.exists():
        raise FileValidationError("file not found")
    if not path.is_file():
        raise FileValidationError("not a regular file")

    extension = path.suffix.lower()
    if extension not in constants.ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(constants.ALLOWED_EXTENSIONS))
        raise FileValidationError(
            f"unsupported extension '{extension or '(none)'}'; allowed: {allowed}"
        )

    size = path.stat().st_size
    if size == 0:
        raise FileValidationError("file is empty")
    if not os.access(path, os.R_OK):
        raise FileValidationError("file is not readable")
    if size > constants.MAX_EMAIL_SIZE_BYTES:
        limit = _megabytes(constants.MAX_EMAIL_SIZE_BYTES)
        raise FileValidationError(f"file exceeds {limit:g} MB ({_megabytes(size):.1f} MB)")
