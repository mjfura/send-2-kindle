"""Local checks that decide whether a file can be sent to Kindle."""

import os
import stat
from pathlib import Path

from send_2_kindle import constants
from send_2_kindle.errors import FileValidationError


def _megabytes(size: int) -> float:
    return size / 1_000_000


def validate_file(path: Path) -> None:
    """Raise FileValidationError with a user-facing reason if ``path`` cannot be sent."""
    # stat() tells "missing" apart from "can't reach it" (Path.exists() reports both as False).
    try:
        info = path.stat()
    except FileNotFoundError:
        raise FileValidationError("file not found") from None
    except PermissionError:
        raise FileValidationError("file is not readable") from None
    if not stat.S_ISREG(info.st_mode):
        raise FileValidationError("not a regular file")

    extension = path.suffix.lower()
    if extension not in constants.ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(constants.ALLOWED_EXTENSIONS))
        raise FileValidationError(
            f"unsupported extension '{extension or '(none)'}'; allowed: {allowed}"
        )

    size = info.st_size
    if size == 0:
        raise FileValidationError("file is empty")
    if not os.access(path, os.R_OK):
        raise FileValidationError("file is not readable")
    if size > constants.MAX_EMAIL_SIZE_BYTES:
        limit = _megabytes(constants.MAX_EMAIL_SIZE_BYTES)
        raise FileValidationError(f"file exceeds {limit:g} MB ({_megabytes(size):.1f} MB)")
