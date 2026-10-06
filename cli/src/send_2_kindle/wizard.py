"""`s2k init`: interactive wizard that writes the user's config file."""

import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import typer
from dotenv import dotenv_values
from pydantic import EmailStr, TypeAdapter, ValidationError

from send_2_kindle import constants
from send_2_kindle.config import SmtpHost, SmtpPort, SmtpSecurity, config_file_path
from send_2_kindle.doctor import report, run_checks

INTRO = """\
s2k init: configure Send to Kindle by email.

You will need:
  - Your Send to Kindle address: Amazon > Manage Your Content and Devices > Preferences >
    Personal Document Settings.
  - The email you send from must be on the "Approved Personal Document E-mail List" (same page).
  - Gmail: an app password, not your account password: {url}
"""
HEADER = "# s2k configuration, written by `s2k init`. Keep it private (chmod 600).\n"

_EMAIL: TypeAdapter[Any] = TypeAdapter(EmailStr)
_HOST: TypeAdapter[Any] = TypeAdapter(SmtpHost)
_PORT: TypeAdapter[Any] = TypeAdapter(SmtpPort)
_SECURITY: TypeAdapter[Any] = TypeAdapter(SmtpSecurity)


def _is_interactive() -> bool:
    return sys.stdin.isatty()


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def write_config(path: Path, values: dict[str, str]) -> None:
    """Atomically write ``values`` as KEY="value" lines to ``path`` (mode 600, new dirs 700)."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    content = HEADER + "".join(f"{key}={_quote(value)}\n" for key, value in values.items())
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=".config.env.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


def _read_existing(path: Path) -> dict[str, str]:
    try:
        values = dotenv_values(path, interpolate=False) if path.is_file() else {}
    except OSError:
        return {}
    return {key: value for key, value in values.items() if value is not None}


def _ask(text: str, adapter: TypeAdapter[Any], default: str | None) -> str:
    while True:
        answer = str(typer.prompt(text, default=default, type=str)).strip()
        try:
            adapter.validate_python(answer)
        except ValidationError as error:
            typer.secho(f"  {error.errors()[0]['msg']}", fg=typer.colors.YELLOW)
        else:
            return answer


def _ask_password(has_current: bool) -> str | None:
    """Return the new password, or None to keep the current one."""
    if has_current:
        answer = typer.prompt(
            "SMTP password (empty keeps the current one)",
            default="",
            hide_input=True,
            show_default=False,
        )
        return str(answer) or None
    return str(typer.prompt("SMTP password", hide_input=True))


def _collect(current: dict[str, str]) -> dict[str, str]:
    values = {
        "S2K_KINDLE_EMAIL": _ask("Send to Kindle address", _EMAIL, current.get("S2K_KINDLE_EMAIL")),
        "S2K_SENDER_EMAIL": _ask("Email you send from", _EMAIL, current.get("S2K_SENDER_EMAIL")),
        "S2K_SMTP_HOST": _ask(
            "SMTP server", _HOST, current.get("S2K_SMTP_HOST", constants.GMAIL_SMTP_HOST)
        ),
        "S2K_SMTP_PORT": _ask("SMTP port", _PORT, current.get("S2K_SMTP_PORT", "587")),
        "S2K_SMTP_SECURITY": _ask(
            "Security (starttls/ssl)", _SECURITY, current.get("S2K_SMTP_SECURITY", "starttls")
        ),
    }
    password = _ask_password(bool(current.get("S2K_SMTP_PASSWORD")))
    values["S2K_SMTP_PASSWORD"] = password if password is not None else current["S2K_SMTP_PASSWORD"]
    if current.get("S2K_SMTP_USERNAME"):
        values["S2K_SMTP_USERNAME"] = current["S2K_SMTP_USERNAME"]
    return values


def run_wizard() -> int:
    """Run the interactive setup and return the process exit code."""
    if not _is_interactive():
        typer.secho(
            "s2k init is interactive; run it in your own terminal.", fg=typer.colors.RED, err=True
        )
        return 2
    path = config_file_path()
    typer.echo(INTRO.format(url=constants.GMAIL_APP_PASSWORDS_URL))
    try:
        values = _collect(_read_existing(path))
    except typer.Abort:
        typer.secho("Aborted; configuration not changed.", fg=typer.colors.RED, err=True)
        return 1
    write_config(path, values)
    typer.echo(f"Saved {path} (permissions 600)")
    try:
        run_now = typer.confirm("Run checks now?", default=True)
    except typer.Abort:
        return 0
    return report(run_checks()) if run_now else 0
