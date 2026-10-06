"""Readiness checks for `s2k doctor` and the end of `s2k init`. Never sends email."""

import os
import platform
import stat
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import typer

from send_2_kindle import installed_version
from send_2_kindle.config import REQUIRED_VARIABLES, config_file_path, load_settings
from send_2_kindle.errors import ConfigError, SmtpAuthError, SmtpConnectionError
from send_2_kindle.mailer import KindleMailer

AMAZON_NOTE = (
    "Amazon cannot be checked without sending. To confirm end to end: s2k send <small-file.txt>"
)


class Status(StrEnum):
    OK = "✓"
    WARN = "⚠"
    FAIL = "✗"
    SKIP = "-"
    INFO = "ℹ"  # noqa: RUF001 - intentional "information" symbol, not the letter i


@dataclass(frozen=True)
class CheckResult:
    status: Status
    message: str


_COLORS: dict[Status, str] = {
    Status.OK: typer.colors.GREEN,
    Status.WARN: typer.colors.YELLOW,
    Status.FAIL: typer.colors.RED,
}


def _display(path: Path) -> str:
    home = Path.home()
    return f"~/{path.relative_to(home)}" if path.is_relative_to(home) else str(path)


def _skipped(*names: str) -> list[CheckResult]:
    return [CheckResult(Status.SKIP, f"{name} (not checked)") for name in names]


def _config_source() -> list[CheckResult]:
    path = config_file_path()
    if path.is_file():
        results = [CheckResult(Status.OK, f"Config file: {_display(path)}")]
        if os.name == "posix" and stat.S_IMODE(path.stat().st_mode) & 0o077:
            results.append(
                CheckResult(
                    Status.WARN,
                    f"Config file is readable by other users → chmod 600 {_display(path)}",
                )
            )
        return results
    if all(os.environ.get(name) for name in REQUIRED_VARIABLES):
        return [
            CheckResult(Status.OK, f"Using environment variables (no file at {_display(path)})")
        ]
    return [
        CheckResult(
            Status.FAIL,
            f"No configuration found at {_display(path)} → run `s2k init` in your terminal",
        )
    ]


def run_checks() -> list[CheckResult]:
    """Run every readiness check in order; later checks are skipped when one fails."""
    results = [
        CheckResult(Status.OK, f"s2k {installed_version()} (Python {platform.python_version()})")
    ]
    amazon = CheckResult(Status.INFO, AMAZON_NOTE)

    results.extend(_config_source())
    if any(result.status is Status.FAIL for result in results):
        return [*results, *_skipped("Settings", "SMTP connection", "SMTP login"), amazon]

    try:
        settings = load_settings()
    except ConfigError as error:
        results.append(CheckResult(Status.FAIL, str(error)))
        return [*results, *_skipped("SMTP connection", "SMTP login"), amazon]
    results.append(
        CheckResult(
            Status.OK,
            f"Settings valid (sender {settings.sender_email} → kindle {settings.kindle_email})",
        )
    )

    connected = CheckResult(
        Status.OK,
        f"Connected to {settings.smtp_host}:{settings.smtp_port} "
        f"({settings.smtp_security.upper()})",
    )
    try:
        with KindleMailer(settings):
            pass
    except SmtpConnectionError as error:
        results.append(CheckResult(Status.FAIL, str(error)))
        results.extend(_skipped("SMTP login"))
    except SmtpAuthError as error:
        results.extend([connected, CheckResult(Status.FAIL, str(error))])
    else:
        results.extend(
            [connected, CheckResult(Status.OK, f"Logged in as {settings.login_username}")]
        )
    results.append(amazon)
    return results


def report(results: list[CheckResult]) -> int:
    """Print the results and return the exit code: 0 when nothing failed, else 1."""
    for result in results:
        typer.secho(f"{result.status} {result.message}", fg=_COLORS.get(result.status))
    failures = sum(result.status is Status.FAIL for result in results)
    if failures:
        typer.secho(f"Not ready: {failures} problem(s).", fg=typer.colors.RED)
        return 1
    typer.secho("Ready.", fg=typer.colors.GREEN)
    return 0
