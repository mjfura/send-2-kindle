"""Command-line entry point: ``s2k FILE...``."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from send_2_kindle import constants, installed_version
from send_2_kindle.config import load_settings
from send_2_kindle.doctor import report, run_checks
from send_2_kindle.errors import (
    ConfigError,
    FileValidationError,
    SendError,
    SmtpAuthError,
    SmtpConnectionError,
)
from send_2_kindle.mailer import KindleMailer
from send_2_kindle.providers import provider_for_host
from send_2_kindle.validation import is_not_downloaded, validate_file
from send_2_kindle.wizard import run_wizard

AMAZON_NOTE = (
    "Note: Amazon may still reject a sent file (e.g. sender not approved); it will email you if so."
)

# Never show local variables in tracebacks: they could include the SMTP password.
app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False, no_args_is_help=True)


def _print_version(value: bool) -> None:
    if value:
        typer.echo(f"s2k {installed_version()}")
        raise typer.Exit()


@app.callback()
def cli(
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_print_version, is_eager=True, help="Show the version and exit."
        ),
    ] = False,
) -> None:
    """Send local files to your Kindle through the Send to Kindle email service."""


@dataclass
class Outcome:
    path: Path
    sent: bool = False
    reason: str = "not sent"


@app.command()
def send(
    files: Annotated[
        list[Path],
        typer.Argument(help="Files to send (pdf, epub, docx, txt, ...).", show_default=False),
    ],
) -> None:
    """Send files to your Kindle, one email per file."""
    try:
        settings = load_settings()
    except ConfigError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from None

    provider = provider_for_host(settings.smtp_host)
    max_bytes = min(constants.MAX_EMAIL_SIZE_BYTES, provider.max_file_bytes) if provider else None
    provider_name = provider.name if provider else None

    outcomes = [Outcome(path) for path in files]
    pending: list[Outcome] = []
    for outcome in outcomes:
        try:
            validate_file(outcome.path, max_bytes=max_bytes, provider_name=provider_name)
        except FileValidationError as error:
            outcome.reason = str(error)
        else:
            pending.append(outcome)

    # Download iCloud Drive files before logging in: a long download would leave the SMTP
    # session idle, and a server that drops it would fail every remaining file.
    ready: list[Outcome] = []
    for outcome in pending:
        if is_not_downloaded(outcome.path):
            typer.echo(f'Downloading "{outcome.path.name}" from iCloud…')
            try:
                _fetch_from_icloud(outcome.path)
            except OSError as error:
                outcome.reason = f"could not download it from iCloud (are you offline?): {error}"
                continue
        ready.append(outcome)
    pending = ready

    if pending:
        try:
            with KindleMailer(settings) as mailer:
                for outcome in pending:
                    try:
                        mailer.send(outcome.path)
                    except SendError as error:
                        outcome.reason = str(error)
                    else:
                        outcome.sent = True
        except (SmtpConnectionError, SmtpAuthError) as error:
            typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)

    _print_report(outcomes)
    if not all(outcome.sent for outcome in outcomes):
        raise typer.Exit(code=1)


@app.command()
def doctor() -> None:
    """Check that s2k is configured and can log in to your SMTP server (sends nothing)."""
    raise typer.Exit(code=report(run_checks()))


@app.command()
def init() -> None:
    """Interactive setup that writes your config file. Run it in your own terminal."""
    raise typer.Exit(code=run_wizard())


def _fetch_from_icloud(path: Path) -> None:
    """Reading a not-downloaded iCloud Drive file makes macOS download it."""
    path.read_bytes()


def _print_report(outcomes: list[Outcome]) -> None:
    width = max(len(str(outcome.path)) for outcome in outcomes)
    for outcome in outcomes:
        name = str(outcome.path).ljust(width)
        if outcome.sent:
            typer.secho(f"✓ {name}  sent", fg=typer.colors.GREEN)
        else:
            typer.secho(f"✗ {name}  {outcome.reason}", fg=typer.colors.RED)
    sent = sum(outcome.sent for outcome in outcomes)
    typer.echo(f"{sent} sent, {len(outcomes) - sent} failed")
    if sent:
        typer.echo(AMAZON_NOTE)
