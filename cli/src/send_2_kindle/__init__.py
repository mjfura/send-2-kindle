"""s2k: send local files to your Kindle through the Send to Kindle email service."""

from importlib.metadata import version

DISTRIBUTION_NAME = "s2k-cli"


def installed_version() -> str:
    """Version of the installed s2k-cli distribution (single source: pyproject.toml)."""
    return version(DISTRIBUTION_NAME)
