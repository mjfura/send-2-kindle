"""Local checks that decide whether a file can be sent to Kindle."""

import os
import stat
from pathlib import Path
from typing import Final

from send_2_kindle import constants
from send_2_kindle.errors import FileValidationError

# macOS marks iCloud Drive files whose contents are not on disk yet ("Optimize Mac Storage").
SF_DATALESS: Final[int] = 0x40000000


def is_not_downloaded(path: Path) -> bool:
    """True for an iCloud Drive file macOS has not downloaded; reading it triggers the download."""
    try:
        flags = getattr(path.stat(), "st_flags", 0)
    except OSError:
        return False
    return bool(flags & SF_DATALESS)


def _megabytes(size: int) -> float:
    return size / 1_000_000


def validate_file(
    path: Path, max_bytes: int | None = None, provider_name: str | None = None
) -> None:
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
    limit_bytes = constants.MAX_EMAIL_SIZE_BYTES if max_bytes is None else max_bytes
    if size > limit_bytes:
        limit = f"{_megabytes(limit_bytes):g} MB"
        where = f", the limit for {provider_name}" if provider_name else ""
        raise FileValidationError(f"file exceeds {limit}{where} ({_megabytes(size):.1f} MB)")
