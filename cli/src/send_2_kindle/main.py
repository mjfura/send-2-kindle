"""Command-line entry point: ``s2k FILE...``."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from send_2_kindle.config import load_settings
from send_2_kindle.errors import (
    ConfigError,
    FileValidationError,
    SendError,
    SmtpAuthError,
    SmtpConnectionError,
)
from send_2_kindle.mailer import KindleMailer
from send_2_kindle.validation import validate_file

AMAZON_NOTE = (
    "Note: Amazon may still reject a sent file (e.g. sender not approved); it will email you if so."
)

# Never show local variables in tracebacks: they could include the SMTP password.
app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)


@dataclass
class Outcome:
    path: Path
    sent: bool = False
    reason: str = "not sent"


@app.command()
def main(
    files: Annotated[
        list[Path],
        typer.Argument(help="Files to send (pdf, epub, docx, txt, ...).", show_default=False),
    ],
) -> None:
    """Send local files to your Kindle through the Send to Kindle email service."""
    try:
        settings = load_settings()
    except ConfigError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from None

    outcomes = [Outcome(path) for path in files]
    pending: list[Outcome] = []
    for outcome in outcomes:
        try:
            validate_file(outcome.path)
        except FileValidationError as error:
            outcome.reason = str(error)
        else:
            pending.append(outcome)

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
