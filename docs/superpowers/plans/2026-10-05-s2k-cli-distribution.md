# s2k CLI Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `s2k` installable by anyone from PyPI, configurable per user with `s2k init`, verifiable with `s2k doctor`, and released automatically from `vX.Y.Z` tags.

**Architecture:** The existing Typer app becomes a command group (`send`, `doctor`, `init`, `--version`). Configuration moves from `cli/.env` to a per-user file resolved by `config_file_path()`. Two new modules: `doctor.py` (check runner + report, reusing `KindleMailer` for connect/login) and `wizard.py` (prompts + atomic private file write). A new tag-triggered workflow verifies, tests, builds, publishes to PyPI with Trusted Publishing and creates the GitHub Release.

**Tech Stack:** Python 3.13, Poetry 2, Typer, pydantic / pydantic-settings, python-dotenv, pytest, ruff, mypy, GitHub Actions, PyPI Trusted Publishing.

**Spec:** `docs/superpowers/specs/2026-10-05-s2k-cli-distribution-design.md`

## Global Constraints

- All code, docs, commits and PR text in English; git per the `git-workflow` skill; branch `feat/cli-distribution`; Conventional Commits with scope `cli` (or `ci`); no AI attribution lines.
- PyPI distribution name `send-2-kindle`; console script `s2k`; license MIT ("Copyright (c) 2026 Marco Fura").
- Single version source: `cli/pyproject.toml` `[project].version`, written in canonical PEP 440 form; stays `0.1.0` in this branch.
- Config resolution, highest first: env vars `S2K_*` → `$S2K_CONFIG_FILE` → `$XDG_CONFIG_HOME/s2k/config.env` → `~/.config/s2k/config.env`. `cli/.env` is no longer read.
- Exit codes: `0` success, `1` operation ran and something failed, `2` configuration or usage error. `doctor` exits only 0 or 1. `init` without a TTY exits 2.
- The SMTP password is never printed, logged, or requested by an agent.
- Tests never use the network, the real user config, or real `S2K_*`/`XDG_CONFIG_HOME`/`HOME` values.
- Third-party GitHub Actions pinned to full commit SHAs: checkout `3d3c42e5aac5ba805825da76410c181273ba90b1` (v7.0.1), setup-python `5fda3b95a4ea91299a34e894583c3862153e4b97` (v7.0.0), upload-artifact `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` (v7.0.1), download-artifact `3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c` (v8.0.1), pypa/gh-action-pypi-publish `dc37677b2e1c63e2034f94d8a5b11f265b73ba33` (v1.14.2).
- Quality gates before every commit (in `cli/`): `poetry run ruff check .`, `poetry run ruff format --check .`, `poetry run mypy src tests`, `poetry run pytest`.
- Deviation from the spec's file table: the wizard module is `wizard.py` (not `init.py`) to avoid confusion with `__init__.py`; the command is still `s2k init`.

## Review Focus

1. **Passwords with special characters** (`p@ss "w0rd" \ #1 $HOME`, spaces) written by `s2k init` must load back byte-for-byte. Test: Task 4 `test_password_with_special_characters_round_trips`.
2. **Unreadable config file** (wrong owner/mode) → `ConfigError` "Cannot read <path>", so `send` exits 2 and `doctor` shows ✗ — never a traceback. Tests: Task 1 `test_unreadable_config_file_is_a_config_error`, Task 3 `test_unreadable_config_file_is_reported`.
3. **`XDG_CONFIG_HOME` set but empty** → falls back to `~/.config` instead of writing to `/s2k/config.env`. Test: Task 1 `test_empty_xdg_config_home_falls_back_to_home`.
4. **`S2K_CONFIG_FILE=~/s2k.env`** (unexpanded tilde, as when set in a `.zshrc` with quotes) → resolves under the home directory. Test: Task 1 `test_config_file_variable_expands_home`.
5. **Existing config file with permissions 644** rewritten by `s2k init` ends with 600. Test: Task 4 `test_existing_values_are_defaults_and_empty_password_keeps_it` (asserts the mode).

---

## File Structure

| File | Responsibility |
|---|---|
| `cli/src/send_2_kindle/__init__.py` | `DISTRIBUTION_NAME`, `installed_version()` |
| `cli/src/send_2_kindle/config.py` | `config_file_path()`, shared field types, `Settings`, `load_settings()` |
| `cli/src/send_2_kindle/main.py` | Typer group: `--version`, `send`, `doctor`, `init` |
| `cli/src/send_2_kindle/doctor.py` (new) | `Status`, `CheckResult`, `run_checks()`, `report()` |
| `cli/src/send_2_kindle/wizard.py` (new) | `write_config()`, prompts, `run_wizard()` |
| `cli/tests/conftest.py` | Isolation: `S2K_CONFIG_FILE`, `HOME`, `XDG_CONFIG_HOME` |
| `cli/tests/test_config.py`, `test_main.py`, `test_doctor.py` (new), `test_wizard.py` (new) | Tests per module |
| `cli/pyproject.toml` | Metadata, `python-dotenv` dependency |
| `LICENSE`, `cli/LICENSE` | MIT |
| `cli/README.md`, `cli/CONTRIBUTING.md` (new), `CLAUDE.md` | User docs, contributor docs, agent notes |
| `cli/.env.example` | Deleted |
| `.github/workflows/cli.yml` | + build-and-install smoke step |
| `.github/workflows/release.yml` (new), `.github/scripts/check_release_version.py` (new) | Release pipeline |
| `docs/releasing.md` (new) | One-time PyPI setup + release procedure |

---

### Task 1: Per-user configuration file

**Files:**
- Modify: `cli/src/send_2_kindle/config.py`, `cli/tests/conftest.py`, `cli/tests/test_config.py`

**Interfaces:**
- Consumes: `constants.GMAIL_SMTP_HOST`, `errors.ConfigError` (unchanged).
- Produces:
  - `config.config_file_path() -> Path` — resolved per Global Constraints; file may not exist.
  - `config.CONFIG_FILE_VARIABLE = "S2K_CONFIG_FILE"`, `config.REQUIRED_VARIABLES: tuple[str, ...] = ("S2K_KINDLE_EMAIL", "S2K_SENDER_EMAIL", "S2K_SMTP_PASSWORD")`.
  - Shared field types `config.SmtpHost`, `config.SmtpPort`, `config.SmtpSecurity` (used by Task 4).
  - `load_settings() -> Settings` reads `config_file_path()`; raises `ConfigError` for invalid values **and** for an unreadable file ("Cannot read <path>: <reason>").
  - `config.PROJECT_DIR` and `config.ENV_FILE` are removed.
  - Fixture `isolated_env` (autouse) now returns the temp config file path (`tmp_path / "config.env"`, set via `S2K_CONFIG_FILE`); `HOME` is `tmp_path / "home"`; `XDG_CONFIG_HOME` unset.

- [ ] **Step 1: Replace the isolation fixture in `cli/tests/conftest.py`**

Replace the `isolated_env` fixture (and its docstring line at the top) with:
```python
"""Shared fixtures. Tests never read the real user config or S2K_* shell variables."""
```
```python
@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    for name in list(os.environ):
        if name.startswith("S2K_"):
            monkeypatch.delenv(name)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    config_file = tmp_path / "config.env"
    monkeypatch.setenv("S2K_CONFIG_FILE", str(config_file))
    return config_file
```
Remove `from send_2_kindle import config` only if it becomes unused (the `settings` fixture still uses `config.load_settings()`, so keep it).

- [ ] **Step 2: Update `cli/tests/test_config.py`**

Delete `test_env_file_lives_in_the_cli_directory`. Add `import os` to the imports. Append:
```python
def test_config_file_variable_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("S2K_CONFIG_FILE", str(tmp_path / "custom.env"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert config.config_file_path() == tmp_path / "custom.env"


def test_config_file_variable_expands_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("S2K_CONFIG_FILE", "~/s2k.env")
    assert config.config_file_path() == tmp_path / "home" / "s2k.env"


def test_xdg_config_home_is_used(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("S2K_CONFIG_FILE")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert config.config_file_path() == tmp_path / "xdg" / "s2k" / "config.env"


def test_default_is_dot_config_in_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("S2K_CONFIG_FILE")
    assert config.config_file_path() == tmp_path / "home" / ".config" / "s2k" / "config.env"


def test_empty_xdg_config_home_falls_back_to_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("S2K_CONFIG_FILE")
    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    assert config.config_file_path() == tmp_path / "home" / ".config" / "s2k" / "config.env"


def test_load_settings_reads_the_resolved_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("S2K_CONFIG_FILE")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    path = tmp_path / "xdg" / "s2k" / "config.env"
    path.parent.mkdir(parents=True)
    path.write_text(REQUIRED_FILE_LINES + "S2K_SMTP_PASSWORD=secret\n")
    assert load_settings().smtp_password.get_secret_value() == "secret"


def test_dot_env_in_working_directory_is_ignored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workdir = tmp_path / "project"
    workdir.mkdir()
    (workdir / ".env").write_text(REQUIRED_FILE_LINES + "S2K_SMTP_PASSWORD=secret\n")
    monkeypatch.chdir(workdir)
    with pytest.raises(ConfigError):
        load_settings()


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0, reason="root can read any file"
)
def test_unreadable_config_file_is_a_config_error(isolated_env: Path) -> None:
    isolated_env.write_text(REQUIRED_FILE_LINES + "S2K_SMTP_PASSWORD=secret\n")
    isolated_env.chmod(0)
    try:
        with pytest.raises(ConfigError, match="Cannot read"):
            load_settings()
    finally:
        isolated_env.chmod(0o600)
```

- [ ] **Step 3: Run tests to verify they fail**

Run (in `cli/`): `poetry run pytest tests/test_config.py -q`
Expected: the new tests FAIL with `AttributeError: module 'send_2_kindle.config' has no attribute 'config_file_path'`, and `test_unreadable_config_file_is_a_config_error` fails (no ConfigError). Earlier tests may also fail because `load_settings()` still reads `cli/.env`.

- [ ] **Step 4: Rewrite `cli/src/send_2_kindle/config.py`**

```python
"""Configuration loaded from S2K_* environment variables and the user's config file."""

import os
from pathlib import Path
from typing import Annotated, Final, Literal

from pydantic import EmailStr, Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from send_2_kindle import constants
from send_2_kindle.errors import ConfigError

ENV_PREFIX: Final[str] = "S2K_"
CONFIG_FILE_VARIABLE: Final[str] = "S2K_CONFIG_FILE"
REQUIRED_VARIABLES: Final[tuple[str, ...]] = (
    "S2K_KINDLE_EMAIL",
    "S2K_SENDER_EMAIL",
    "S2K_SMTP_PASSWORD",
)

# Field types shared by Settings and the `s2k init` wizard, so both validate the same way.
SmtpHost = Annotated[str, Field(min_length=1)]
SmtpPort = Annotated[int, Field(ge=1, le=65535)]
SmtpSecurity = Literal["starttls", "ssl"]


def config_file_path() -> Path:
    """Return the config file s2k reads (it may not exist).

    $S2K_CONFIG_FILE, else $XDG_CONFIG_HOME/s2k/config.env, else ~/.config/s2k/config.env.
    """
    override = os.environ.get(CONFIG_FILE_VARIABLE)
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or "~/.config"
    return Path(base).expanduser() / "s2k" / "config.env"


class Settings(BaseSettings):
    """Validated s2k configuration. Real environment variables override the config file."""

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX, env_file_encoding="utf-8", extra="ignore"
    )

    kindle_email: EmailStr
    sender_email: EmailStr
    smtp_password: SecretStr
    smtp_host: SmtpHost = constants.GMAIL_SMTP_HOST
    smtp_port: SmtpPort = 587
    smtp_security: SmtpSecurity = "starttls"
    smtp_username: str | None = None

    @field_validator("smtp_password")
    @classmethod
    def _password_not_empty(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value():
            raise ValueError("must not be empty")
        return value

    @property
    def login_username(self) -> str:
        """SMTP login: S2K_SMTP_USERNAME, or the sender address when unset or empty."""
        return self.smtp_username or self.sender_email


def _describe(error: ValidationError, path: Path) -> str:
    lines = [f"Invalid configuration (check {path} or your environment variables):"]
    for item in error.errors():
        field = str(item["loc"][0]) if item["loc"] else "?"
        reason = "is required" if item["type"] == "missing" else item["msg"]
        lines.append(f"  {ENV_PREFIX}{field.upper()}: {reason}")
    return "\n".join(lines)


def load_settings() -> Settings:
    """Load settings from the environment and config_file_path(), raising ConfigError if invalid."""
    path = config_file_path()
    try:
        return Settings(_env_file=path)
    except ValidationError as error:
        raise ConfigError(_describe(error, path)) from None
    except OSError as error:
        raise ConfigError(f"Cannot read {path}: {error.strerror or error}") from None
```

- [ ] **Step 5: Run tests and quality gates**

Run: `poetry run pytest -q && poetry run ruff check . && poetry run ruff format --check . && poetry run mypy src tests`
Expected: all pass (previous 74 minus 1 removed plus 8 new = 81). If `ruff format --check` fails, run `poetry run ruff format .` and re-run.

- [ ] **Step 6: Commit**

```bash
git add cli/src/send_2_kindle/config.py cli/tests/conftest.py cli/tests/test_config.py
git commit -m "feat(cli)!: read config from the user config directory" -m "BREAKING CHANGE: cli/.env is no longer read; use ~/.config/s2k/config.env, XDG_CONFIG_HOME or S2K_CONFIG_FILE."
```

---

### Task 2: Subcommands and `--version`

**Files:**
- Modify: `cli/src/send_2_kindle/__init__.py`, `cli/src/send_2_kindle/main.py`, `cli/tests/test_main.py`

**Interfaces:**
- Consumes: `load_settings()`, `validate_file()`, `KindleMailer`, errors.
- Produces:
  - `send_2_kindle.DISTRIBUTION_NAME = "send-2-kindle"`, `send_2_kindle.installed_version() -> str`.
  - `main.app` is a Typer group (`no_args_is_help=True`) with eager `--version` printing `s2k <version>`, and command `send FILES...` (unchanged behaviour). Tasks 3 and 4 add `doctor` and `init` to this `app`.

- [ ] **Step 1: Rewrite `cli/tests/test_main.py`**

```python
import smtplib
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from send_2_kindle import installed_version
from send_2_kindle.main import app
from tests.fakes import FakeSMTPServer

runner = CliRunner()


def _file(directory: Path, name: str, content: bytes = b"data") -> Path:
    path = directory / name
    path.write_bytes(content)
    return path


def _send(*paths: Path) -> list[str]:
    return ["send", *(str(path) for path in paths)]


def _subjects(server: FakeSMTPServer) -> list[str]:
    return [str(message["Subject"]) for message in server.sent]


@pytest.mark.usefixtures("valid_env")
def test_sends_every_valid_file(fake_smtp: FakeSMTPServer, tmp_path: Path) -> None:
    result = runner.invoke(app, _send(_file(tmp_path, "a.epub"), _file(tmp_path, "b.pdf")))
    assert result.exit_code == 0, result.output
    assert "2 sent, 0 failed" in result.output
    assert "Amazon may still reject" in result.output
    assert _subjects(fake_smtp) == ["a.epub", "b.pdf"]


@pytest.mark.usefixtures("valid_env")
def test_invalid_file_is_reported_and_others_are_sent(
    fake_smtp: FakeSMTPServer, tmp_path: Path
) -> None:
    result = runner.invoke(app, _send(_file(tmp_path, "a.epub"), _file(tmp_path, "b.mobi")))
    assert result.exit_code == 1
    assert "unsupported extension" in result.output
    assert "1 sent, 1 failed" in result.output
    assert _subjects(fake_smtp) == ["a.epub"]


@pytest.mark.usefixtures("valid_env")
def test_does_not_connect_when_no_file_is_valid(fake_smtp: FakeSMTPServer, tmp_path: Path) -> None:
    result = runner.invoke(app, _send(tmp_path / "missing.pdf"))
    assert result.exit_code == 1
    assert "file not found" in result.output
    assert "0 sent, 1 failed" in result.output
    assert "Amazon may still reject" not in result.output
    assert fake_smtp.calls == []


def test_config_error_exits_2_without_connecting(fake_smtp: FakeSMTPServer, tmp_path: Path) -> None:
    result = runner.invoke(app, _send(_file(tmp_path, "a.epub")))
    assert result.exit_code == 2
    assert "S2K_KINDLE_EMAIL" in result.output
    assert fake_smtp.calls == []


@pytest.mark.usefixtures("valid_env")
def test_auth_failure_aborts_and_marks_files_not_sent(
    fake_smtp: FakeSMTPServer, tmp_path: Path
) -> None:
    fake_smtp.login_error = smtplib.SMTPAuthenticationError(535, b"bad credentials")
    result = runner.invoke(app, _send(_file(tmp_path, "a.epub"), _file(tmp_path, "b.pdf")))
    assert result.exit_code == 1
    assert "authentication failed" in result.output
    assert "not sent" in result.output
    assert "0 sent, 2 failed" in result.output
    assert "app-password" not in result.output


@pytest.mark.usefixtures("valid_env")
def test_send_error_on_one_file_continues_with_the_rest(
    fake_smtp: FakeSMTPServer, tmp_path: Path
) -> None:
    fake_smtp.send_errors["a.epub"] = smtplib.SMTPDataError(552, b"message too large")
    result = runner.invoke(app, _send(_file(tmp_path, "a.epub"), _file(tmp_path, "b.pdf")))
    assert result.exit_code == 1
    assert "552 message too large" in result.output
    assert "1 sent, 1 failed" in result.output
    assert _subjects(fake_smtp) == ["b.pdf"]


@pytest.mark.usefixtures("valid_env")
def test_connection_lost_mid_run_marks_remaining_files_not_sent(
    fake_smtp: FakeSMTPServer, tmp_path: Path
) -> None:
    fake_smtp.send_errors["a.epub"] = smtplib.SMTPServerDisconnected("gone")
    result = runner.invoke(app, _send(_file(tmp_path, "a.epub"), _file(tmp_path, "b.pdf")))
    assert result.exit_code == 1
    assert "connection lost" in result.output
    assert "0 sent, 2 failed" in result.output
    assert _subjects(fake_smtp) == []


def test_send_requires_at_least_one_file() -> None:
    result = runner.invoke(app, ["send"])
    assert result.exit_code == 2


def test_files_without_subcommand_are_not_sent(fake_smtp: FakeSMTPServer, tmp_path: Path) -> None:
    result = runner.invoke(app, [str(_file(tmp_path, "a.epub"))])
    assert result.exit_code == 2
    assert fake_smtp.calls == []


def test_no_arguments_shows_help_with_send_command() -> None:
    result = runner.invoke(app, [])
    assert "send" in result.output
    assert "Usage" in result.output


def test_version_option_prints_installed_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == f"s2k {installed_version()}"


def test_installed_version_matches_pyproject() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text())["project"]["version"]
    assert installed_version() == declared
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/test_main.py -q`
Expected: collection error `ImportError: cannot import name 'installed_version' from 'send_2_kindle'`.

- [ ] **Step 3: Implement**

`cli/src/send_2_kindle/__init__.py`:
```python
"""s2k: send local files to your Kindle through the Send to Kindle email service."""

from importlib.metadata import version

DISTRIBUTION_NAME = "send-2-kindle"


def installed_version() -> str:
    """Version of the installed send-2-kindle distribution (single source: pyproject.toml)."""
    return version(DISTRIBUTION_NAME)
```

In `cli/src/send_2_kindle/main.py`:
- Add `from send_2_kindle import installed_version` to the imports.
- Replace the `app = typer.Typer(...)` line with:
```python
# Never show local variables in tracebacks: they could include the SMTP password.
app = typer.Typer(
    add_completion=False, pretty_exceptions_show_locals=False, no_args_is_help=True
)


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
```
  (delete the old comment line above `app` so it is not duplicated).
- Rename the command function `main` to `send` and change its docstring to `"""Send files to your Kindle, one email per file."""`. Body unchanged.

- [ ] **Step 4: Run tests and quality gates**

Run: `poetry run pytest -q && poetry run ruff check . && poetry run ruff format --check . && poetry run mypy src tests`
Expected: all pass. Then `poetry run s2k --version` → `s2k 0.1.0`; `poetry run s2k` → help listing `send`.

- [ ] **Step 5: Commit**

```bash
git add cli/src/send_2_kindle/__init__.py cli/src/send_2_kindle/main.py cli/tests/test_main.py
git commit -m "feat(cli)!: move sending to s2k send and add --version" -m "BREAKING CHANGE: 's2k FILE...' is now 's2k send FILE...'."
```

---

### Task 3: `s2k doctor`

**Files:**
- Create: `cli/src/send_2_kindle/doctor.py`, `cli/tests/test_doctor.py`
- Modify: `cli/src/send_2_kindle/main.py`

**Interfaces:**
- Consumes: `installed_version()`, `config_file_path()`, `REQUIRED_VARIABLES`, `load_settings()`, `KindleMailer`, `ConfigError`, `SmtpConnectionError`, `SmtpAuthError`.
- Produces:
  - `doctor.Status` (`StrEnum`: `OK="✓"`, `WARN="⚠"`, `FAIL="✗"`, `SKIP="-"`, `INFO="ℹ"`), `doctor.CheckResult(status: Status, message: str)` (frozen dataclass).
  - `doctor.run_checks() -> list[CheckResult]` — never sends email.
  - `doctor.report(results: list[CheckResult]) -> int` — prints one line per result plus `Ready.` / `Not ready: <n> problem(s).`; returns 0 when no `FAIL`, else 1. Used by Task 4.
  - Command `s2k doctor`.

- [ ] **Step 1: Write the failing tests**

`cli/tests/test_doctor.py`:
```python
import os
import smtplib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from send_2_kindle.main import app
from tests.fakes import FakeSMTPServer

runner = CliRunner()


def _write_config(path: Path, kindle: str = "reader@kindle.com") -> None:
    path.write_text(
        f"S2K_KINDLE_EMAIL={kindle}\nS2K_SENDER_EMAIL=me@gmail.com\nS2K_SMTP_PASSWORD=app-password\n"
    )
    path.chmod(0o600)


def test_all_checks_pass(isolated_env: Path, fake_smtp: FakeSMTPServer) -> None:
    _write_config(isolated_env)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert f"Config file: {isolated_env}" in result.output
    assert "Settings valid (sender me@gmail.com → kindle reader@kindle.com)" in result.output
    assert "Connected to smtp.gmail.com:587 (STARTTLS)" in result.output
    assert "Logged in as me@gmail.com" in result.output
    assert "Amazon cannot be checked without sending" in result.output
    assert result.output.rstrip().endswith("Ready.")
    assert not any(call.startswith("send:") for call in fake_smtp.calls)
    assert "app-password" not in result.output


def test_missing_config_points_to_init(fake_smtp: FakeSMTPServer) -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "run `s2k init` in your terminal" in result.output
    assert "SMTP login (not checked)" in result.output
    assert "Not ready: 1 problem(s)." in result.output
    assert fake_smtp.calls == []


@pytest.mark.usefixtures("valid_env")
def test_environment_only_config_is_accepted(fake_smtp: FakeSMTPServer) -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "Using environment variables" in result.output


def test_partial_environment_config_is_not_enough(
    fake_smtp: FakeSMTPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("S2K_KINDLE_EMAIL", "reader@kindle.com")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "No configuration found" in result.output


def test_permissive_file_warns_but_passes(isolated_env: Path, fake_smtp: FakeSMTPServer) -> None:
    _write_config(isolated_env)
    isolated_env.chmod(0o644)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "⚠" in result.output
    assert "chmod 600" in result.output


def test_invalid_settings_fail_without_echoing_values(
    isolated_env: Path, fake_smtp: FakeSMTPServer
) -> None:
    _write_config(isolated_env, kindle="not-an-email")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "S2K_KINDLE_EMAIL" in result.output
    assert "not-an-email" not in result.output
    assert fake_smtp.calls == []


def test_connection_failure_skips_login(isolated_env: Path, fake_smtp: FakeSMTPServer) -> None:
    _write_config(isolated_env)
    fake_smtp.connect_error = ConnectionRefusedError("refused")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "could not connect to smtp.gmail.com:587" in result.output
    assert "SMTP login (not checked)" in result.output


def test_auth_failure_reports_connection_ok(isolated_env: Path, fake_smtp: FakeSMTPServer) -> None:
    _write_config(isolated_env)
    fake_smtp.login_error = smtplib.SMTPAuthenticationError(535, b"bad credentials")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "Connected to smtp.gmail.com:587 (STARTTLS)" in result.output
    assert "app password" in result.output
    assert "app-password" not in result.output


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0, reason="root can read any file"
)
def test_unreadable_config_file_is_reported(isolated_env: Path, fake_smtp: FakeSMTPServer) -> None:
    _write_config(isolated_env)
    isolated_env.chmod(0)
    try:
        result = runner.invoke(app, ["doctor"])
    finally:
        isolated_env.chmod(0o600)
    assert result.exit_code == 1
    assert "Cannot read" in result.output
    assert fake_smtp.calls == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/test_doctor.py -q`
Expected: every test FAILS — `s2k doctor` is not a command yet (exit code 2, "No such command 'doctor'").

- [ ] **Step 3: Implement `cli/src/send_2_kindle/doctor.py`**

```python
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
    "Amazon cannot be checked without sending. "
    "To confirm end to end: s2k send <small-file.txt>"
)


class Status(StrEnum):
    OK = "✓"
    WARN = "⚠"
    FAIL = "✗"
    SKIP = "-"
    INFO = "ℹ"


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
        return [CheckResult(Status.OK, f"Using environment variables (no file at {_display(path)})")]
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
```

In `cli/src/send_2_kindle/main.py` add `from send_2_kindle.doctor import report, run_checks` and, after the `send` command:
```python
@app.command()
def doctor() -> None:
    """Check that s2k is configured and can log in to your SMTP server (sends nothing)."""
    raise typer.Exit(code=report(run_checks()))
```

- [ ] **Step 4: Run tests and quality gates**

Run: `poetry run pytest -q && poetry run ruff check . && poetry run ruff format --check . && poetry run mypy src tests`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add cli/src/send_2_kindle/doctor.py cli/src/send_2_kindle/main.py cli/tests/test_doctor.py
git commit -m "feat(cli): add s2k doctor readiness checks"
```

---

### Task 4: `s2k init` wizard

**Files:**
- Create: `cli/src/send_2_kindle/wizard.py`, `cli/tests/test_wizard.py`
- Modify: `cli/src/send_2_kindle/main.py`, `cli/pyproject.toml` / `cli/poetry.lock` (add `python-dotenv`)

**Interfaces:**
- Consumes: `config_file_path()`, `SmtpHost`, `SmtpPort`, `SmtpSecurity`, `load_settings()` (tests), `doctor.run_checks()`, `doctor.report()`, `constants.GMAIL_SMTP_HOST`, `constants.GMAIL_APP_PASSWORDS_URL`.
- Produces:
  - `wizard.write_config(path: Path, values: dict[str, str]) -> None` — atomic, file mode 600, new parent dir mode 700, values double-quoted with `\` and `"` escaped.
  - `wizard._is_interactive() -> bool` (patched in tests), `wizard.run_wizard() -> int` (exit code).
  - Command `s2k init`.

- [ ] **Step 1: Add the dependency**

Run (in `cli/`): `poetry add "python-dotenv (>=1.2,<2.0)"`
Expected: `pyproject.toml` lists it under `[project].dependencies` and the lock file updates.

- [ ] **Step 2: Write the failing tests**

`cli/tests/test_wizard.py`:
```python
import stat
from pathlib import Path

import pytest
from typer.testing import CliRunner

from send_2_kindle import wizard
from send_2_kindle.config import load_settings
from send_2_kindle.main import app
from tests.fakes import FakeSMTPServer

runner = CliRunner()

PASSWORD = "abcd efgh ijkl mnop"


def _answers(*lines: str) -> str:
    return "\n".join(lines) + "\n"


# kindle, sender, host, port, security, password, "run checks now?"
NEW_CONFIG = _answers("reader@kindle.com", "me@gmail.com", "", "", "", PASSWORD, "n")


@pytest.fixture
def interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wizard, "_is_interactive", lambda: True)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_requires_an_interactive_terminal(isolated_env: Path) -> None:
    result = runner.invoke(app, ["init"], input=NEW_CONFIG)
    assert result.exit_code == 2
    assert "run it in your own terminal" in result.output
    assert not isolated_env.exists()


@pytest.mark.usefixtures("interactive")
def test_writes_private_config_that_loads(isolated_env: Path) -> None:
    result = runner.invoke(app, ["init"], input=NEW_CONFIG)
    assert result.exit_code == 0, result.output
    assert f"Saved {isolated_env} (permissions 600)" in result.output
    assert _mode(isolated_env) == 0o600
    settings = load_settings()
    assert settings.kindle_email == "reader@kindle.com"
    assert settings.sender_email == "me@gmail.com"
    assert settings.smtp_host == "smtp.gmail.com"
    assert settings.smtp_port == 587
    assert settings.smtp_security == "starttls"
    assert settings.smtp_password.get_secret_value() == PASSWORD
    assert PASSWORD not in result.output


@pytest.mark.usefixtures("interactive")
def test_creates_missing_directory_with_private_permissions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "fresh" / "s2k" / "config.env"
    monkeypatch.setenv("S2K_CONFIG_FILE", str(path))
    result = runner.invoke(app, ["init"], input=NEW_CONFIG)
    assert result.exit_code == 0, result.output
    assert _mode(path.parent) == 0o700
    assert _mode(path) == 0o600


@pytest.mark.usefixtures("interactive")
def test_invalid_email_is_asked_again(isolated_env: Path) -> None:
    answers = _answers(
        "not-an-email", "reader@kindle.com", "me@gmail.com", "", "", "", PASSWORD, "n"
    )
    result = runner.invoke(app, ["init"], input=answers)
    assert result.exit_code == 0, result.output
    assert "not a valid email address" in result.output
    assert load_settings().kindle_email == "reader@kindle.com"


@pytest.mark.usefixtures("interactive")
def test_invalid_port_is_asked_again(isolated_env: Path) -> None:
    answers = _answers(
        "reader@kindle.com", "me@gmail.com", "", "70000", "465", "ssl", PASSWORD, "n"
    )
    result = runner.invoke(app, ["init"], input=answers)
    assert result.exit_code == 0, result.output
    assert "less than or equal to 65535" in result.output
    settings = load_settings()
    assert settings.smtp_port == 465
    assert settings.smtp_security == "ssl"


@pytest.mark.usefixtures("interactive")
def test_existing_values_are_defaults_and_empty_password_keeps_it(isolated_env: Path) -> None:
    wizard.write_config(
        isolated_env,
        {
            "S2K_KINDLE_EMAIL": "old@kindle.com",
            "S2K_SENDER_EMAIL": "old@gmail.com",
            "S2K_SMTP_HOST": "smtp.example.com",
            "S2K_SMTP_PORT": "2525",
            "S2K_SMTP_SECURITY": "starttls",
            "S2K_SMTP_PASSWORD": "old secret",
            "S2K_SMTP_USERNAME": "login-user",
        },
    )
    isolated_env.chmod(0o644)
    result = runner.invoke(app, ["init"], input=_answers("", "", "", "", "", "", "n"))
    assert result.exit_code == 0, result.output
    assert "[old@kindle.com]" in result.output
    settings = load_settings()
    assert settings.kindle_email == "old@kindle.com"
    assert settings.smtp_host == "smtp.example.com"
    assert settings.smtp_port == 2525
    assert settings.smtp_password.get_secret_value() == "old secret"
    assert settings.smtp_username == "login-user"
    assert _mode(isolated_env) == 0o600


@pytest.mark.usefixtures("interactive")
def test_password_with_special_characters_round_trips(isolated_env: Path) -> None:
    password = 'p@ss "w0rd" \\ #1 $HOME'
    answers = _answers("reader@kindle.com", "me@gmail.com", "", "", "", password, "n")
    result = runner.invoke(app, ["init"], input=answers)
    assert result.exit_code == 0, result.output
    assert load_settings().smtp_password.get_secret_value() == password


@pytest.mark.usefixtures("interactive")
def test_abort_writes_nothing(isolated_env: Path) -> None:
    result = runner.invoke(app, ["init"], input=_answers("reader@kindle.com"))
    assert result.exit_code == 1
    assert "configuration not changed" in result.output
    assert not isolated_env.exists()


@pytest.mark.usefixtures("interactive")
def test_running_checks_uses_the_doctor_exit_code(
    isolated_env: Path, fake_smtp: FakeSMTPServer
) -> None:
    answers = _answers("reader@kindle.com", "me@gmail.com", "", "", "", PASSWORD, "y")
    result = runner.invoke(app, ["init"], input=answers)
    assert result.exit_code == 0, result.output
    assert "Logged in as me@gmail.com" in result.output
    assert result.output.rstrip().endswith("Ready.")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `poetry run pytest tests/test_wizard.py -q`
Expected: collection error `ImportError: cannot import name 'wizard' from 'send_2_kindle'`.

- [ ] **Step 4: Implement `cli/src/send_2_kindle/wizard.py`**

```python
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
        "S2K_KINDLE_EMAIL": _ask(
            "Send to Kindle address", _EMAIL, current.get("S2K_KINDLE_EMAIL")
        ),
        "S2K_SENDER_EMAIL": _ask(
            "Email you send from", _EMAIL, current.get("S2K_SENDER_EMAIL")
        ),
        "S2K_SMTP_HOST": _ask(
            "SMTP server", _HOST, current.get("S2K_SMTP_HOST", constants.GMAIL_SMTP_HOST)
        ),
        "S2K_SMTP_PORT": _ask("SMTP port", _PORT, current.get("S2K_SMTP_PORT", "587")),
        "S2K_SMTP_SECURITY": _ask(
            "Security (starttls/ssl)", _SECURITY, current.get("S2K_SMTP_SECURITY", "starttls")
        ),
    }
    password = _ask_password(bool(current.get("S2K_SMTP_PASSWORD")))
    values["S2K_SMTP_PASSWORD"] = (
        password if password is not None else current["S2K_SMTP_PASSWORD"]
    )
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
```

In `cli/src/send_2_kindle/main.py` add `from send_2_kindle.wizard import run_wizard` and, after `doctor`:
```python
@app.command()
def init() -> None:
    """Interactive setup that writes your config file. Run it in your own terminal."""
    raise typer.Exit(code=run_wizard())
```

- [ ] **Step 5: Run tests and quality gates**

Run: `poetry run pytest -q && poetry run ruff check . && poetry run ruff format --check . && poetry run mypy src tests`
Expected: all pass. Then `poetry run s2k` → help lists `send`, `doctor`, `init`.

- [ ] **Step 6: Commit**

```bash
git add cli/pyproject.toml cli/poetry.lock cli/src/send_2_kindle/wizard.py cli/src/send_2_kindle/main.py cli/tests/test_wizard.py
git commit -m "feat(cli): add s2k init setup wizard"
```

---

### Task 5: Package metadata, license and documentation

**Files:**
- Create: `LICENSE`, `cli/LICENSE`, `cli/CONTRIBUTING.md`
- Modify: `cli/pyproject.toml`, `cli/README.md`, `CLAUDE.md`, `.github/workflows/cli.yml`
- Delete: `cli/.env.example`

**Interfaces:**
- Consumes: commands from Tasks 2–4.
- Produces: a wheel/sdist named `send-2-kindle` with MIT license metadata; PR CI step that installs the built wheel and runs `s2k --version`.

- [ ] **Step 1: Create `LICENSE` and copy it to `cli/LICENSE`**

```text
MIT License

Copyright (c) 2026 Marco Fura

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
Run: `cp LICENSE cli/LICENSE`

- [ ] **Step 2: Add metadata to `[project]` in `cli/pyproject.toml`**

After `readme = "README.md"` add:
```toml
license = "MIT"
license-files = ["LICENSE"]
keywords = ["kindle", "send-to-kindle", "ebook", "email", "cli"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: End Users/Desktop",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.13",
    "Topic :: Communications :: Email",
]
```
And after the `[project.scripts]` table add:
```toml
[project.urls]
Homepage = "https://github.com/mjfura/send-2-kindle"
Repository = "https://github.com/mjfura/send-2-kindle"
Issues = "https://github.com/mjfura/send-2-kindle/issues"
```

- [ ] **Step 3: Verify the built package**

Run (in `cli/`):
```bash
rm -rf dist && poetry build
unzip -p dist/send_2_kindle-0.1.0-py3-none-any.whl 'send_2_kindle-0.1.0.dist-info/METADATA' | grep -E '^(Name|Version|License|Project-URL|Requires-Dist)'
unzip -l dist/send_2_kindle-0.1.0-py3-none-any.whl | grep -i license
SMOKE=$(mktemp -d) && python3.13 -m venv "$SMOKE/venv" && "$SMOKE/venv/bin/pip" install -q dist/send_2_kindle-0.1.0-py3-none-any.whl && "$SMOKE/venv/bin/s2k" --version && "$SMOKE/venv/bin/s2k" --help | head -5 && rm -rf "$SMOKE" dist
```
Expected: `Name: send-2-kindle`, `Version: 0.1.0`, a `License` line containing MIT, three `Project-URL` lines, `Requires-Dist` for typer/pydantic/pydantic-settings/email-validator/python-dotenv; a LICENSE file inside the wheel; `s2k 0.1.0`; help listing the three commands.

- [ ] **Step 4: Add the packaging smoke step to `.github/workflows/cli.yml`** (after the `Test` step)

```yaml
      - name: Build and smoke-test the package
        if: steps.changes.outputs.run == 'true'
        working-directory: cli
        run: |
          poetry build
          python3.13 -m venv /tmp/s2k-smoke
          /tmp/s2k-smoke/bin/pip install dist/*.whl
          /tmp/s2k-smoke/bin/s2k --version
```

- [ ] **Step 5: Rewrite `cli/README.md` for end users**

````markdown
# s2k — send files to your Kindle

`s2k` emails documents to your Kindle through Amazon's Send to Kindle service, one email per file.

```bash
s2k send book.epub paper.pdf notes.docx
```

Supported: `.pdf .epub .doc .docx .txt .rtf .html .htm .jpg .jpeg .png .gif .bmp`, up to 50 MB
each (your email provider may allow less: Gmail rejects files above roughly 18 MB).

## Install

Requires Python 3.13+.

```bash
pipx install send-2-kindle       # or: uv tool install send-2-kindle
```

## Set up

1. **In Amazon** (*Manage Your Content and Devices → Preferences → Personal Document Settings*):
   copy your `@kindle.com` address and add the email you will send from to the *Approved Personal
   Document E-mail List*.
2. **Gmail users:** create an app password at <https://myaccount.google.com/apppasswords>
   (requires 2-Step Verification). Your normal Gmail password will not work.
3. Run the wizard in your terminal — it asks for the values, hides the password, saves them to
   `~/.config/s2k/config.env` with private permissions and offers to test the login:
   ```bash
   s2k init
   ```
4. Check that everything is ready at any time (sends nothing):
   ```bash
   s2k doctor
   ```

## Usage

```bash
s2k send FILE...    # send files, one email each
s2k doctor          # check configuration and SMTP login
s2k init            # create or update the configuration
s2k --version
```

Exit codes: `0` success · `1` something failed (see the report) · `2` invalid configuration or usage.

"Sent" means your email provider accepted the message. If Amazon rejects it (for example, the
sender is not approved), Amazon emails you.

## Configuration

Read from, highest priority first: environment variables → the file in `S2K_CONFIG_FILE` →
`$XDG_CONFIG_HOME/s2k/config.env` → `~/.config/s2k/config.env`.

| Variable | Required | Default |
|---|---|---|
| `S2K_KINDLE_EMAIL` | yes | — |
| `S2K_SENDER_EMAIL` | yes | — |
| `S2K_SMTP_PASSWORD` | yes | — |
| `S2K_SMTP_HOST` | no | `smtp.gmail.com` |
| `S2K_SMTP_PORT` | no | `587` |
| `S2K_SMTP_SECURITY` | no | `starttls` (`ssl` for port 465) |
| `S2K_SMTP_USERNAME` | no | the sender address |

## Troubleshooting

| `s2k doctor` says | Do this |
|---|---|
| No configuration found | Run `s2k init` |
| authentication failed … app password | Create a Gmail app password and run `s2k init` again |
| could not connect | Check `S2K_SMTP_HOST`, `S2K_SMTP_PORT` and `S2K_SMTP_SECURITY` |
| Config file is readable by other users | `chmod 600 ~/.config/s2k/config.env` |

## License

MIT
````

- [ ] **Step 6: Create `cli/CONTRIBUTING.md`**

````markdown
# Contributing to s2k

Python 3.13 + Poetry. The virtualenv lives in `cli/.venv`.

```bash
cd cli
poetry env use python3.13
poetry install
```

Run before every commit:
```bash
poetry run ruff check . && poetry run ruff format --check . && poetry run mypy src tests && poetry run pytest
```

- Tests never send real email (a fake SMTP replaces `smtplib`) and never read your real
  configuration (`tests/conftest.py` points `S2K_CONFIG_FILE` and `HOME` to temp paths).
- Design docs: `docs/superpowers/specs/`. Releases: `docs/releasing.md`.
- Git workflow: Conventional Commits, `<type>/<kebab-case>` branches, squash-merged PRs.

## Manual smoke test

With your real configuration (`s2k init`):
```bash
echo "s2k smoke test" > /tmp/s2k-smoke.txt
poetry run s2k send /tmp/s2k-smoke.txt
```
````

- [ ] **Step 7: Update `CLAUDE.md` and delete the old template**

Replace the `## CLI (\`cli/\`)` section of `CLAUDE.md` with:
```markdown
## CLI (`cli/`)

Python 3.13 + Poetry project published to PyPI as `send-2-kindle` (command `s2k`); virtualenv in `cli/.venv`.
Designs: `docs/superpowers/specs/2026-10-05-s2k-cli-design.md`, `docs/superpowers/specs/2026-10-05-s2k-cli-distribution-design.md`. Releases: `docs/releasing.md`.
Run from `cli/` before every commit: `poetry run ruff check . && poetry run ruff format --check . && poetry run mypy src tests && poetry run pytest`.
Tests must never send real email or read the real user config. Never ask the user for their SMTP password: they run `s2k init` themselves.
```
Run: `git rm cli/.env.example`

- [ ] **Step 8: Run quality gates and commit**

Run (in `cli/`): `poetry run pytest -q && poetry run ruff check . && poetry run ruff format --check . && poetry run mypy src tests`
Expected: all pass.
```bash
git add LICENSE cli/LICENSE cli/pyproject.toml cli/README.md cli/CONTRIBUTING.md CLAUDE.md .github/workflows/cli.yml
git commit -m "docs(cli): prepare the package for pypi with mit license and user docs"
```

---

### Task 6: Release workflow

**Files:**
- Create: `.github/scripts/check_release_version.py`, `.github/workflows/release.yml`, `docs/releasing.md`

**Interfaces:**
- Consumes: `cli/pyproject.toml` version; quality-gate commands; wheel smoke test from Task 5.
- Produces: tag `v*` → PyPI publication (environment `pypi`) + GitHub Release; GitHub environment `pypi` exists on the repo.

- [ ] **Step 1: Create `.github/scripts/check_release_version.py`**

```python
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
```

- [ ] **Step 2: Check the script locally**

Run (repo root):
```bash
python3.13 .github/scripts/check_release_version.py v0.1.0 cli/pyproject.toml; echo "exit=$?"
python3.13 .github/scripts/check_release_version.py v0.1.1 cli/pyproject.toml; echo "exit=$?"
python3.13 .github/scripts/check_release_version.py v0.1.0-rc.1 cli/pyproject.toml; echo "exit=$?"
python3.13 .github/scripts/check_release_version.py vnope cli/pyproject.toml; echo "exit=$?"
```
Expected: first `Tag v0.1.0 matches …` exit 0; the other three print `::error::…` and exit 1. If `packaging` is missing locally, run with `uvx --with packaging==26.3 python3.13 …` instead.

- [ ] **Step 3: Create `.github/workflows/release.yml`**

```yaml
# Publish send-2-kindle to PyPI and create a GitHub Release when a vX.Y.Z tag is pushed.
name: release

on:
  push:
    tags: ["v*"]

permissions:
  contents: read

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: "3.13"
      - name: Tag matches cli/pyproject.toml version
        run: |
          python -m pip install --quiet "packaging==26.3"
          python .github/scripts/check_release_version.py "$GITHUB_REF_NAME" cli/pyproject.toml
      - name: Tagged commit is on main
        run: |
          git fetch --quiet origin main
          git merge-base --is-ancestor "$GITHUB_SHA" origin/main

  test:
    needs: verify
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: "3.13"
      - name: Install Poetry
        run: pipx install --python python3.13 poetry==2.1.1
      - name: Lint, type-check and test
        working-directory: cli
        run: |
          poetry install --no-interaction
          poetry run ruff check .
          poetry run ruff format --check .
          poetry run mypy src tests
          poetry run pytest

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: "3.13"
      - name: Install Poetry
        run: pipx install --python python3.13 poetry==2.1.1
      - name: Build and smoke-test
        working-directory: cli
        run: |
          poetry build
          python3.13 -m venv /tmp/s2k-smoke
          /tmp/s2k-smoke/bin/pip install dist/*.whl
          test "$(/tmp/s2k-smoke/bin/s2k --version)" = "s2k $(poetry version --short)"
      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          name: dist
          path: cli/dist/
          if-no-files-found: error

  publish:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: pypi
      url: https://pypi.org/project/send-2-kindle/
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
        with:
          name: dist
          path: dist/
      - uses: pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33 # v1.14.2

  github-release:
    needs: publish
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
        with:
          name: dist
          path: dist/
      - name: Create GitHub Release
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          prerelease=""
          case "$GITHUB_REF_NAME" in *-*) prerelease="--prerelease" ;; esac
          gh release create "$GITHUB_REF_NAME" --repo "$GITHUB_REPOSITORY" \
            --verify-tag --generate-notes $prerelease dist/*
```
Run: `python3.13 -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml')); print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Create `docs/releasing.md`**

````markdown
# Releasing send-2-kindle

One version for the whole repository. A `vX.Y.Z` tag on `main` publishes the CLI to PyPI
(`send-2-kindle`) and creates a GitHub Release (`.github/workflows/release.yml`).

## One-time setup (owner)

1. Create a PyPI account at <https://pypi.org/account/register/> and enable 2FA.
2. *Your account → Publishing → Add a new pending publisher* (GitHub tab):
   - PyPI project name: `send-2-kindle`
   - Owner: `mjfura` · Repository: `send-2-kindle`
   - Workflow name: `release.yml` · Environment name: `pypi`
3. The GitHub environment `pypi` already exists in the repository settings (*Settings →
   Environments*). Optionally add yourself as a required reviewer to approve each publication.

No tokens or passwords are stored anywhere: PyPI trusts this workflow through OIDC.

## Each release

1. Pick the version: `~/.claude/skills/git-workflow/scripts/next-version.sh --verbose`.
2. If it differs from `cli/pyproject.toml`, open a PR `chore(release): vX.Y.Z` that changes only
   `version` (canonical PEP 440 form, e.g. `0.2.0rc1` for `v0.2.0-rc.1`) and merge it.
3. Tag and push:
   ```bash
   git switch main && git pull --ff-only
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin vX.Y.Z
   ```
4. Watch it: `gh run watch $(gh run list --workflow release.yml --limit 1 --json databaseId --jq '.[0].databaseId')`.
5. Smoke test from a clean environment: `pipx install send-2-kindle==X.Y.Z && s2k --version`.

If any job before `publish` fails, nothing is published: fix on `main` and tag again with the next
version (PyPI never accepts the same version twice; tags are protected from being moved).
Pre-release tags (`-rc.N`) publish PyPI pre-releases that `pipx install` ignores unless asked.
````

- [ ] **Step 5: Create the GitHub environment `pypi`**

Run: `gh api -X PUT repos/mjfura/send-2-kindle/environments/pypi --jq .name`
Expected: `pypi`.

- [ ] **Step 6: Commit**

```bash
git add .github/scripts/check_release_version.py .github/workflows/release.yml docs/releasing.md
git commit -m "ci(cli): publish to pypi and create a github release on version tags"
```

---

### Task 7: Pull request and rollout

**Files:** none (git/GitHub operations and owner steps).

**Interfaces:**
- Consumes: everything above.
- Produces: merged PR; the owner's config migrated; first release `v0.1.0` (owner-approved).

- [ ] **Step 1: Push and open the PR**

```bash
git push -u origin feat/cli-distribution
gh pr create --base main --title "feat(cli)!: make s2k installable from pypi with init and doctor" --body "$(cat <<'EOF'
## What

- `s2k send`, `s2k doctor`, `s2k init` and `s2k --version` (subcommands replace `s2k FILE...`).
- Per-user config: env vars → `S2K_CONFIG_FILE` → `$XDG_CONFIG_HOME/s2k/config.env` → `~/.config/s2k/config.env`; `cli/.env` is no longer read.
- PyPI packaging as `send-2-kindle` (MIT), user README, CONTRIBUTING, release workflow with Trusted Publishing.

## Why

Let anyone install and configure the CLI, as the base for the s2k Claude Code plugin.

## How it was tested

- pytest (config resolution, doctor, init wizard, send), ruff, mypy --strict.
- Built wheel installed in a clean venv: `s2k --version` and `--help`.
- Release version check run locally against matching and mismatching tags.

## Notes for reviewers

BREAKING CHANGE: `s2k FILE...` is now `s2k send FILE...`; config moves out of `cli/.env`.
Spec: docs/superpowers/specs/2026-10-05-s2k-cli-distribution-design.md
EOF
)"
```

- [ ] **Step 2: Wait for checks**

Run: `gh pr checks --watch`
Expected: `cli` and `conventions` pass (the `cli` log shows the new "Build and smoke-test the package" step printing `s2k 0.1.0`).

- [ ] **Step 3: Owner migrates their config (ask first)**

Ask the owner, then run:
```bash
mkdir -p ~/.config/s2k && chmod 700 ~/.config/s2k
mv cli/.env ~/.config/s2k/config.env && chmod 600 ~/.config/s2k/config.env
cd cli && poetry run s2k doctor
```
Expected: `Ready.` (real SMTP login, no email sent).

- [ ] **Step 4: Merge (owner decides)**

```bash
gh pr merge --squash --admin
git switch main && git pull --ff-only && git branch -D feat/cli-distribution
```

- [ ] **Step 5: First release (owner completes PyPI setup, then approves the tag)**

The owner follows "One-time setup" in `docs/releasing.md`. Only after they confirm, and approve
publishing `v0.1.0` (irreversible on PyPI):
```bash
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
```
Expected: `release` workflow green; <https://pypi.org/project/send-2-kindle/0.1.0/> exists; GitHub
Release `v0.1.0` with the wheel and sdist attached. Then in a clean shell:
`pipx install send-2-kindle && s2k --version && s2k doctor`.
