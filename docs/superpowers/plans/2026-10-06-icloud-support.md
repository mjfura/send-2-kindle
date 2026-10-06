# iCloud Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make iCloud Mail a first-class provider (presets in `s2k init`, provider-specific hints and size limits) and send not-downloaded iCloud Drive files by downloading them automatically, with matching plugin guidance.

**Architecture:** A new `providers.py` registry (Gmail, iCloud) is looked up from `S2K_SMTP_HOST`; `mailer` uses it for auth hints, `main.send` for size limits, `wizard` for presets. `validation.is_not_downloaded()` reads macOS's `SF_DATALESS` flag; `main.send` announces the download and `KindleMailer.send` maps a failed read of such a file to an iCloud-specific error. Plugin skills, the fake CLI and one eval case follow.

**Tech Stack:** Python 3.13, Typer, pydantic, pytest/ruff/mypy (CLI); Markdown skills, POSIX sh stub, `claude plugin eval` (plugin).

**Spec:** `docs/superpowers/specs/2026-10-06-icloud-support-design.md`

## Global Constraints

- English everywhere; git per `git-workflow`; branch `feat/icloud-support`; scopes `cli`, `plugin`; no AI attribution.
- Providers: Gmail `smtp.gmail.com` 587 starttls, max file 18 000 000 bytes, "app password", `https://myaccount.google.com/apppasswords`; iCloud `smtp.mail.me.com` 587 starttls, max file 14 000 000 bytes, "app-specific password", `https://account.apple.com`. Unknown host: Amazon's 50 000 000.
- Provider comes from `S2K_SMTP_HOST` only (case-insensitive, trimmed); no new setting.
- `SF_DATALESS = 0x40000000`; `is_not_downloaded` never raises and is false where `st_flags` does not exist.
- Messages: `file exceeds 14 MB, the limit for iCloud (16.2 MB)`; `Downloading "<name>" from iCloud…`; `could not download it from iCloud (are you offline?): <error>`; auth: `. iCloud requires an app-specific password, not your account password: https://account.apple.com`.
- CLI gates before each commit (in `cli/`): ruff check, ruff format --check, mypy src tests, pytest. Plugin gates: `claude plugin validate --strict plugin`, `sh plugin/evals/stub/test_stub.sh`.
- Evals, the real iCloud Drive send, merge and release each need the owner's approval.

## Review Focus

1. **iCloud host typed with different case or spaces** (`SMTP.Mail.Me.com `) → still recognized as iCloud (hint and limit). Test: Task 1 `test_provider_for_host_ignores_case_and_spaces`.
2. **Existing config with a custom host** run through `init` → defaults to `other` and keeps the host. Test: Task 3 `test_unknown_existing_host_defaults_to_other`.
3. **A not-downloaded file that is also too large** → rejected by size before any download. Test: Task 2 `test_oversized_cloud_file_is_rejected_before_download`.
4. **Mixed batch, one iCloud file fails to download** → others still sent, exit 1. Test: Task 2 `test_failed_icloud_download_does_not_stop_other_files`.
5. **Non-macOS stat without `st_flags`** → treated as downloaded. Test: Task 2 `test_is_not_downloaded_without_st_flags`.

---

### Task 1: Provider registry and provider-specific auth hints

**Files:** Create `cli/src/send_2_kindle/providers.py`, `cli/tests/test_providers.py`; modify `cli/src/send_2_kindle/constants.py`, `config.py`, `mailer.py`, `cli/tests/test_mailer.py`.

**Interfaces:** Produces `providers.Provider` (frozen dataclass: `key, name, host, port, security, max_file_bytes, password_name, password_url`), `providers.GMAIL`, `providers.ICLOUD`, `providers.PROVIDERS`, `provider_for_host(host: str) -> Provider | None`, `provider_for_key(key: str) -> Provider | None`. Removes `constants.GMAIL_SMTP_HOST`, `constants.GMAIL_APP_PASSWORDS_URL`.

- [ ] **Step 1: Failing tests** — `cli/tests/test_providers.py`:
```python
from send_2_kindle import constants
from send_2_kindle.providers import GMAIL, ICLOUD, PROVIDERS, provider_for_host, provider_for_key


def test_known_hosts_map_to_providers() -> None:
    assert provider_for_host("smtp.gmail.com") is GMAIL
    assert provider_for_host("smtp.mail.me.com") is ICLOUD


def test_provider_for_host_ignores_case_and_spaces() -> None:
    assert provider_for_host("  SMTP.Mail.Me.com ") is ICLOUD


def test_unknown_host_has_no_provider() -> None:
    assert provider_for_host("smtp.example.com") is None


def test_provider_for_key() -> None:
    assert provider_for_key("icloud") is ICLOUD
    assert provider_for_key("other") is None


def test_provider_limits_are_below_amazons() -> None:
    for provider in PROVIDERS:
        assert provider.max_file_bytes < constants.MAX_EMAIL_SIZE_BYTES
```
Append to `cli/tests/test_mailer.py`:
```python
@pytest.mark.usefixtures("valid_env")
def test_icloud_auth_failure_mentions_app_specific_password(
    fake_smtp: FakeSMTPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("S2K_SMTP_HOST", "smtp.mail.me.com")
    fake_smtp.login_error = smtplib.SMTPAuthenticationError(535, b"bad credentials")
    with pytest.raises(SmtpAuthError, match="app-specific password.*account.apple.com"), KindleMailer(
        load_settings()
    ):
        pass
```
Run: `poetry run pytest tests/test_providers.py tests/test_mailer.py -q` → Expected: import error / failing iCloud test.

- [ ] **Step 2: Implement** — `cli/src/send_2_kindle/providers.py`:
```python
"""Known email providers: SMTP settings, attachment limits and where to get their passwords."""

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Provider:
    key: str
    name: str
    host: str
    port: int
    security: str
    # Message limits (Gmail 25 MB, iCloud 20 MB) minus ~33 % base64 growth, rounded down.
    max_file_bytes: int
    password_name: str
    password_url: str


GMAIL: Final = Provider(
    "gmail", "Gmail", "smtp.gmail.com", 587, "starttls", 18_000_000,
    "app password", "https://myaccount.google.com/apppasswords",
)  # fmt: skip
ICLOUD: Final = Provider(
    "icloud", "iCloud", "smtp.mail.me.com", 587, "starttls", 14_000_000,
    "app-specific password", "https://account.apple.com",
)  # fmt: skip
PROVIDERS: Final[tuple[Provider, ...]] = (GMAIL, ICLOUD)


def provider_for_host(host: str) -> Provider | None:
    """Return the provider whose SMTP server is ``host`` (case and spaces ignored)."""
    normalized = host.strip().lower()
    return next((provider for provider in PROVIDERS if provider.host == normalized), None)


def provider_for_key(key: str) -> Provider | None:
    return next((provider for provider in PROVIDERS if provider.key == key), None)
```
In `constants.py` delete the two `GMAIL_*` lines. In `config.py` replace `from send_2_kindle import constants` usage for the default host: import `from send_2_kindle.providers import GMAIL` and set `smtp_host: SmtpHost = GMAIL.host` (keep `constants` import only if still used). In `mailer.py`:
```python
from send_2_kindle.providers import provider_for_host
...
def _auth_failure_message(settings: Settings) -> str:
    message = f"authentication failed for {settings.login_username} on {settings.smtp_host}"
    provider = provider_for_host(settings.smtp_host)
    if provider is not None:
        message += (
            f". {provider.name} requires an {provider.password_name}, not your account password: "
            f"{provider.password_url}"
        )
    return message
```
Fix every remaining `constants.GMAIL_*` reference (`wizard.py` is rewritten in Task 3; for now use `GMAIL.host` / `GMAIL.password_url`): `grep -rn GMAIL_ src tests` must print nothing.

- [ ] **Step 3: Gates** — all CLI gates green. Commit: `feat(cli): add provider registry with icloud auth hints`.

---

### Task 2: Provider size limits and iCloud Drive downloads

**Files:** Modify `cli/src/send_2_kindle/validation.py`, `main.py`, `mailer.py`; tests in `cli/tests/test_validation.py`, `test_main.py`, `test_mailer.py`.

**Interfaces:** Produces `validation.SF_DATALESS`, `validation.is_not_downloaded(path: Path) -> bool`, `validate_file(path: Path, max_bytes: int | None = None, provider_name: str | None = None) -> None` (`None` → `constants.MAX_EMAIL_SIZE_BYTES`, read at call time).

- [ ] **Step 1: Failing tests**

`test_validation.py` (add `from types import SimpleNamespace` and `from send_2_kindle import validation`):
```python
def test_size_limit_names_the_provider(tmp_path: Path) -> None:
    with pytest.raises(FileValidationError, match=r"file exceeds 1e-05 MB, the limit for iCloud"):
        validate_file(_file(tmp_path, "big.pdf", b"x" * 11), max_bytes=10, provider_name="iCloud")


def test_is_not_downloaded_reads_the_dataless_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _file(tmp_path, "cloud.pdf")
    monkeypatch.setattr(Path, "stat", lambda self, **_: SimpleNamespace(st_flags=validation.SF_DATALESS))
    assert validation.is_not_downloaded(path)
    monkeypatch.setattr(Path, "stat", lambda self, **_: SimpleNamespace(st_flags=0))
    assert not validation.is_not_downloaded(path)


def test_is_not_downloaded_without_st_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _file(tmp_path, "local.pdf")
    monkeypatch.setattr(Path, "stat", lambda self, **_: SimpleNamespace())
    assert not validation.is_not_downloaded(path)


def test_is_not_downloaded_on_missing_file(tmp_path: Path) -> None:
    assert not validation.is_not_downloaded(tmp_path / "missing.pdf")
```
`test_main.py` (add `import errno`, `from send_2_kindle import mailer as mailer_module, main as main_module`):
```python
@pytest.mark.usefixtures("valid_env")
def test_icloud_limit_applies_to_icloud_senders(
    fake_smtp: FakeSMTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("S2K_SMTP_HOST", "smtp.mail.me.com")
    big = tmp_path / "big.pdf"
    with big.open("wb") as handle:
        handle.write(b"%PDF")
        handle.truncate(16_200_000)
    result = runner.invoke(app, _send(big))
    assert result.exit_code == 1
    assert "the limit for iCloud (16.2 MB)" in result.output
    assert fake_smtp.calls == []


@pytest.mark.usefixtures("valid_env")
def test_gmail_limit_is_18_mb(fake_smtp: FakeSMTPServer, tmp_path: Path) -> None:
    big = tmp_path / "big.pdf"
    with big.open("wb") as handle:
        handle.write(b"%PDF")
        handle.truncate(18_500_000)
    result = runner.invoke(app, _send(big))
    assert "the limit for Gmail" in result.output


@pytest.mark.usefixtures("valid_env")
def test_cloud_file_download_is_announced(
    fake_smtp: FakeSMTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main_module, "is_not_downloaded", lambda path: path.name == "cloud.pdf")
    result = runner.invoke(app, _send(_file(tmp_path, "cloud.pdf")))
    assert result.exit_code == 0, result.output
    assert 'Downloading "cloud.pdf" from iCloud…' in result.output


@pytest.mark.usefixtures("valid_env")
def test_oversized_cloud_file_is_rejected_before_download(
    fake_smtp: FakeSMTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main_module, "is_not_downloaded", lambda path: True)
    big = tmp_path / "cloud.pdf"
    with big.open("wb") as handle:
        handle.write(b"%PDF")
        handle.truncate(19_000_000)
    result = runner.invoke(app, _send(big))
    assert "Downloading" not in result.output
    assert "the limit for Gmail" in result.output


@pytest.mark.usefixtures("valid_env")
def test_failed_icloud_download_does_not_stop_other_files(
    fake_smtp: FakeSMTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cloud, local = _file(tmp_path, "cloud.pdf"), _file(tmp_path, "local.pdf")
    monkeypatch.setattr(main_module, "is_not_downloaded", lambda path: path.name == "cloud.pdf")
    monkeypatch.setattr(mailer_module, "is_not_downloaded", lambda path: path.name == "cloud.pdf")
    real_build = mailer_module.build_message

    def build(settings, path):  # type: ignore[no-untyped-def]
        if path.name == "cloud.pdf":
            raise OSError(errno.ETIMEDOUT, "Operation timed out")
        return real_build(settings, path)

    monkeypatch.setattr(mailer_module, "build_message", build)
    result = runner.invoke(app, _send(cloud, local))
    assert result.exit_code == 1
    assert "could not download it from iCloud (are you offline?)" in result.output
    assert "1 sent, 1 failed" in result.output
    assert _subjects(fake_smtp) == ["local.pdf"]
```
Run: expected failures (unexpected keyword `max_bytes`, missing `is_not_downloaded`).

- [ ] **Step 2: Implement**

`validation.py`:
```python
from typing import Final
...
# macOS marks iCloud Drive files whose contents are not on disk yet ("Optimize Mac Storage").
SF_DATALESS: Final[int] = 0x40000000


def is_not_downloaded(path: Path) -> bool:
    """True for an iCloud Drive file macOS has not downloaded; reading it triggers the download."""
    try:
        flags = getattr(path.stat(), "st_flags", 0)
    except OSError:
        return False
    return bool(flags & SF_DATALESS)
```
and in `validate_file` add parameters `max_bytes: int | None = None, provider_name: str | None = None`; replace the size block with:
```python
    limit_bytes = constants.MAX_EMAIL_SIZE_BYTES if max_bytes is None else max_bytes
    if size > limit_bytes:
        limit = f"{_megabytes(limit_bytes):g} MB"
        where = f", the limit for {provider_name}" if provider_name else ""
        raise FileValidationError(f"file exceeds {limit}{where} ({_megabytes(size):.1f} MB)")
```
`main.py` (`send`): after loading settings,
```python
    provider = provider_for_host(settings.smtp_host)
    max_bytes = (
        min(constants.MAX_EMAIL_SIZE_BYTES, provider.max_file_bytes) if provider else None
    )
```
call `validate_file(outcome.path, max_bytes=max_bytes, provider_name=provider.name if provider else None)`, and inside the send loop before `mailer.send(outcome.path)`:
```python
                    if is_not_downloaded(outcome.path):
                        typer.echo(f'Downloading "{outcome.path.name}" from iCloud…')
```
(imports: `from send_2_kindle import constants`, `from send_2_kindle.providers import provider_for_host`, `from send_2_kindle.validation import is_not_downloaded, validate_file`).
`mailer.py` `send()`: replace the `build_message` try block with:
```python
        try:
            message = build_message(self._settings, path)
        except OSError as error:
            if is_not_downloaded(path):
                raise SendError(f"could not download it from iCloud (are you offline?): {error}") from error
            raise SendError(f"could not read file: {error}") from error
```
(import `from send_2_kindle.validation import is_not_downloaded`).

- [ ] **Step 3: Gates** — all CLI gates green. Commit: `feat(cli): apply provider size limits and download icloud drive files`.

---

### Task 3: Provider presets in `s2k init`

**Files:** Modify `cli/src/send_2_kindle/wizard.py`, `cli/tests/test_wizard.py`.

**Interfaces:** Consumes `providers.PROVIDERS`, `provider_for_host`, `provider_for_key`, `GMAIL`.

- [ ] **Step 1: Update and add tests** — the provider is now the **first** answer; known providers skip host/port/security. Update the answer lists in `test_wizard.py`:
  - `NEW_CONFIG = _answers("", "reader@kindle.com", "me@gmail.com", PASSWORD, PASSWORD, "n")`
  - invalid email: `_answers("", "not-an-email", "reader@kindle.com", "me@gmail.com", PASSWORD, PASSWORD, "n")`
  - invalid port: `_answers("other", "reader@kindle.com", "me@gmail.com", "", "70000", "465", "ssl", PASSWORD, PASSWORD, "n")`
  - existing values: `_answers("", "", "", "", "", "", "", "n")` (other: host, port, security, then empty password keeps it)
  - special characters: `_answers("", "reader@kindle.com", "me@gmail.com", password, password, "n")`
  - running checks: `_answers("", "reader@kindle.com", "me@gmail.com", PASSWORD, PASSWORD, "y")`
  - mismatch: `_answers("", "reader@kindle.com", "me@gmail.com", "first try", "typo", PASSWORD, PASSWORD, "n")`

Append:
```python
@pytest.mark.usefixtures("interactive")
def test_icloud_preset_fills_the_server_settings(isolated_env: Path) -> None:
    answers = _answers("icloud", "reader@kindle.com", "me@icloud.com", PASSWORD, PASSWORD, "n")
    result = runner.invoke(app, ["init"], input=answers)
    assert result.exit_code == 0, result.output
    assert "account.apple.com" in result.output
    assert "SMTP server" not in result.output
    settings = load_settings()
    assert (settings.smtp_host, settings.smtp_port, settings.smtp_security) == ("smtp.mail.me.com", 587, "starttls")


@pytest.mark.usefixtures("interactive")
def test_existing_icloud_config_defaults_to_icloud(isolated_env: Path) -> None:
    wizard.write_config(isolated_env, {
        "S2K_KINDLE_EMAIL": "reader@kindle.com", "S2K_SENDER_EMAIL": "me@icloud.com",
        "S2K_SMTP_HOST": "smtp.mail.me.com", "S2K_SMTP_PORT": "587",
        "S2K_SMTP_SECURITY": "starttls", "S2K_SMTP_PASSWORD": "secret",
    })  # fmt: skip
    result = runner.invoke(app, ["init"], input=_answers("", "", "", "", "n"))
    assert result.exit_code == 0, result.output
    assert "[icloud]" in result.output
    assert load_settings().smtp_host == "smtp.mail.me.com"


@pytest.mark.usefixtures("interactive")
def test_unknown_existing_host_defaults_to_other(isolated_env: Path) -> None:
    wizard.write_config(isolated_env, {
        "S2K_KINDLE_EMAIL": "reader@kindle.com", "S2K_SENDER_EMAIL": "me@example.com",
        "S2K_SMTP_HOST": "smtp.example.com", "S2K_SMTP_PORT": "2525",
        "S2K_SMTP_SECURITY": "starttls", "S2K_SMTP_PASSWORD": "secret",
    })  # fmt: skip
    result = runner.invoke(app, ["init"], input=_answers("", "", "", "", "", "", "", "n"))
    assert result.exit_code == 0, result.output
    assert "[other]" in result.output
    assert load_settings().smtp_host == "smtp.example.com"
```
Run: expected failures.

- [ ] **Step 2: Implement** in `wizard.py`:
  - imports: `from typing import Any, Literal` and `from send_2_kindle.providers import GMAIL, PROVIDERS, Provider, provider_for_host, provider_for_key`; drop `constants` if unused.
  - `_PROVIDER: TypeAdapter[Any] = TypeAdapter(Literal["gmail", "icloud", "other"])`.
  - `INTRO` passwords line generated from `PROVIDERS`:
    ```python
    INTRO = """\
    s2k init: configure Send to Kindle by email.

    You will need:
      - Your Send to Kindle address: Amazon > Manage Your Content and Devices > Preferences >
        Personal Document Settings.
      - The email you send from must be on the "Approved Personal Document E-mail List" (same page).
    {passwords}
    """
    PASSWORD_LINES = "\n".join(
        f"  - {p.name}: an {p.password_name}, not your account password: {p.password_url}" for p in PROVIDERS
    )
    ```
    and `typer.echo(INTRO.format(passwords=PASSWORD_LINES))` in `run_wizard`.
  - `_collect`:
    ```python
    def _collect(current: dict[str, str]) -> dict[str, str]:
        existing_host = current.get("S2K_SMTP_HOST")
        known = provider_for_host(existing_host) if existing_host else GMAIL
        provider = provider_for_key(_ask("Email provider (gmail/icloud/other)", _PROVIDER, known.key if known else "other"))
        sender_label = "Email you send from"
        if provider is not None and provider.key == "icloud":
            sender_label += " (your iCloud Mail address, e.g. name@icloud.com)"
        values = {
            "S2K_KINDLE_EMAIL": _ask("Send to Kindle address", _EMAIL, current.get("S2K_KINDLE_EMAIL")),
            "S2K_SENDER_EMAIL": _ask(sender_label, _EMAIL, current.get("S2K_SENDER_EMAIL")),
        }
        if provider is not None:
            values |= {
                "S2K_SMTP_HOST": provider.host,
                "S2K_SMTP_PORT": str(provider.port),
                "S2K_SMTP_SECURITY": provider.security,
            }
            typer.echo(f"  {provider.name} needs an {provider.password_name}: {provider.password_url}")
        else:
            values |= {
                "S2K_SMTP_HOST": _ask("SMTP server", _HOST, current.get("S2K_SMTP_HOST", GMAIL.host)),
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
    ```

- [ ] **Step 3: Gates** — all CLI gates green; `grep -rn GMAIL_ src tests` empty. Commit: `feat(cli): offer gmail and icloud presets in s2k init`.

---

### Task 4: Plugin, fake CLI, eval case and docs

**Files:** Modify `plugin/evals/stub/s2k`, `plugin/evals/stub/test_stub.sh`, `plugin/skills/setup/SKILL.md`, `plugin/skills/kindle/SKILL.md`, `plugin/skills/kindle/references/formats.md`, `cli/README.md`, `plugin/README.md`; create `plugin/evals/setup-explains-icloud-auth-failure/`.

- [ ] **Step 1: Failing stub test** — in `test_stub.sh`, after the `doctor auth-fail` check add:
```sh
check "doctor auth-fail-icloud" 1 "app-specific password" auth-fail-icloud doctor
check "send auth-fail-icloud" 1 "account.apple.com" auth-fail-icloud send books/dune.epub
```
Run `sh plugin/evals/stub/test_stub.sh` → 2 failures.

- [ ] **Step 2: Stub** — at the top of `plugin/evals/stub/s2k`, after `version=...`:
```sh
host=smtp.gmail.com sender=reader@gmail.com
auth_error="authentication failed for reader@gmail.com on smtp.gmail.com. Gmail requires an app password, not your account password: https://myaccount.google.com/apppasswords"
if [ "$scenario" = auth-fail-icloud ]; then
  host=smtp.mail.me.com sender=reader@icloud.com
  auth_error="authentication failed for reader@icloud.com on smtp.mail.me.com. iCloud requires an app-specific password, not your account password: https://account.apple.com"
fi
```
remove the old `auth_error=` line, use `$sender`/`$host` in the doctor lines (`Settings valid (sender $sender → …)`, `Connected to $host:587 (STARTTLS)`, `Logged in as $sender`), and replace the two `[ "$scenario" = auth-fail ]` tests with `case "$scenario" in auth-fail|auth-fail-icloud) … esac` equivalents. Run the stub tests → all pass.

- [ ] **Step 3: Skills**
  - `setup/SKILL.md`: after the intro add
    ```markdown
    ## Providers

    | Provider | Server (filled in by `s2k init`) | Password to create |
    |---|---|---|
    | Gmail | `smtp.gmail.com`, 587, starttls | App password: https://myaccount.google.com/apppasswords (2-Step Verification required) |
    | iCloud Mail | `smtp.mail.me.com`, 587, starttls | App-specific password: https://account.apple.com → Sign-In and Security (two-factor authentication required). Send from the full iCloud address (name@icloud.com) |
    | Other | asked by `s2k init` | the provider's SMTP password |
    ```
    change the doctor table's auth row to: `| ✗ authentication failed … | The provider needs an app password (Gmail) or an app-specific password (iCloud), not the account password — the error line gives the link; then `s2k init` again |`; in "Prerequisites" item 3 write `For Gmail an app password, for iCloud an app-specific password (see Providers).`
  - `kindle/SKILL.md` Rules line about limits → `… up to 50 MB per file (Gmail: about 18 MB, iCloud: about 14 MB), not empty. Files in iCloud Drive that are not downloaded are downloaded automatically when sent; warn the user before sending many or large ones.`
  - `references/formats.md` last line → `Limits: 50 MB per file at Amazon; Gmail refuses files above ~18 MB and iCloud Mail above ~14 MB (base64 makes attachments ~33 % larger).`
  - Run `claude plugin validate --strict plugin` → passes.

- [ ] **Step 4: Eval case** — copy `plugin/evals/setup-explains-auth-failure` to `plugin/evals/setup-explains-icloud-auth-failure`; in `case.yaml` set `name: setup-explains-icloud-auth-failure`; in `prompt.md` set `EVAL_S2K_SCENARIO: auth-fail-icloud` and the body `I set up s2k with my iCloud email. Is it ready to send things to my Kindle?`; replace `graders/criteria.md` with:
```markdown
---
type: llm
---

PASS if the final message says s2k is not ready because the login failed, explains that iCloud needs an app-specific password (created at account.apple.com) rather than the Apple ID password, and tells the user to run `s2k init` again.
FAIL if it says s2k is ready, mentions only Gmail app passwords, or does not explain the app-specific password.
```

- [ ] **Step 5: Docs** — `cli/README.md`: in "Set up" step 2 replace the Gmail-only sentence with a providers table (Gmail / iCloud Mail / Other: server filled by `s2k init`, password to create, file limit); add under Usage: `Files in iCloud Drive that are not downloaded yet are downloaded automatically when sent (you need a connection).`; update the size line at the top: `up to 50 MB each (Gmail allows about 18 MB, iCloud Mail about 14 MB)`. `plugin/README.md` Requirements: mention Gmail or iCloud Mail.

- [ ] **Step 6: Commit** — `feat(plugin): guide icloud mail setup and icloud drive sends` (stub, test, skills, eval case, docs).

---

### Task 5: Verification, PR and release (owner approvals)

- [ ] **Step 1 (owner approves):** `S2K_EVAL_MAX_COST=2 plugin/evals/run.sh --case 'setup-*' --runs 1 --ablation none` → every case 1.00 (5 cases). Fix skill wording for failures; report reruns first.
- [ ] **Step 2 (owner approves):** real send of one not-downloaded iCloud Drive PDF with the owner's configuration (`cd cli && poetry run s2k send "<path>"`) → shows `Downloading … from iCloud…` and `1 sent, 0 failed`; the owner confirms it arrived.
- [ ] **Step 3:** push, PR `feat(cli): add icloud mail presets and icloud drive downloads`, wait for `cli`, `conventions`, `plugin`.
- [ ] **Step 4:** final whole-branch review (fresh reviewer), fix Critical/Important with TDD.
- [ ] **Step 5 (owner approves):** merge; release PR bumping both versions to `0.3.0`; tag `v0.3.0`; verify PyPI and the GitHub Release.
