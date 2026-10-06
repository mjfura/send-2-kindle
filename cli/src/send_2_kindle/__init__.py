"""s2k: send local files to your Kindle through the Send to Kindle email service."""

from importlib.metadata import version

DISTRIBUTION_NAME = "send-2-kindle"


def installed_version() -> str:
    """Version of the installed send-2-kindle distribution (single source: pyproject.toml)."""
    return version(DISTRIBUTION_NAME)
