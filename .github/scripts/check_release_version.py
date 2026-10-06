"""Fail unless a release tag matches the version in cli/pyproject.toml (PEP 440 aware).

Usage: python check_release_version.py <tag> <path/to/pyproject.toml>
"""

import sys
import tomllib
from pathlib import Path

from packaging.version import InvalidVersion, Version


def check(tag: str, pyproject: Path) -> str | None:
    """Return an error message, or None when the tag matches the declared version."""
    declared = tomllib.loads(pyproject.read_text())["project"]["version"]
    try:
        tag_version = Version(tag.removeprefix("v"))
    except InvalidVersion:
        return f"Tag {tag} is not a valid version"
    if str(Version(declared)) != declared:
        return f"Version {declared} in {pyproject} is not canonical; write {Version(declared)}"
    if tag_version != Version(declared):
        return f"Tag {tag} does not match version {declared} in {pyproject}"
    return None


if __name__ == "__main__":
    error = check(sys.argv[1], Path(sys.argv[2]))
    if error:
        print(f"::error::{error}")
        sys.exit(1)
    print(f"Tag {sys.argv[1]} matches {sys.argv[2]}")
