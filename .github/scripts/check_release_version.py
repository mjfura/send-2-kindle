"""Fail unless a release tag matches the version of every manifest (PEP 440 aware).

Usage: python check_release_version.py <tag> <manifest> [<manifest> ...]
A .toml manifest is read from [project].version; a .json manifest from its "version" key.
"""

import json
import sys
import tomllib
from pathlib import Path

from packaging.version import InvalidVersion, Version


def declared_version(path: Path) -> str:
    if path.suffix == ".toml":
        return str(tomllib.loads(path.read_text())["project"]["version"])
    return str(json.loads(path.read_text())["version"])


def check(tag: str, manifests: list[Path]) -> str | None:
    """Return an error message, or None when every manifest matches the tag."""
    try:
        tag_version = Version(tag.removeprefix("v"))
    except InvalidVersion:
        return f"Tag {tag} is not a valid version"
    for path in manifests:
        declared = declared_version(path)
        try:
            version = Version(declared)
        except InvalidVersion:
            return f"Version {declared} in {path} is not a valid version"
        if str(version) != declared:
            return f"Version {declared} in {path} is not canonical; write {version}"
        if version != tag_version:
            return f"Tag {tag} does not match version {declared} in {path}"
    return None


if __name__ == "__main__":
    error = check(sys.argv[1], [Path(arg) for arg in sys.argv[2:]])
    if error:
        print(f"::error::{error}")
        sys.exit(1)
    print(f"Tag {sys.argv[1]} matches {', '.join(sys.argv[2:])}")
