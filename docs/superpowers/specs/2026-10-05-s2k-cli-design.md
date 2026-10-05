# s2k CLI — Design

- **Date:** 2026-10-05
- **Status:** Draft, pending review
- **Branch:** `feat/s2k-cli`

## 1. Goal

A minimal command-line tool, `s2k`, that sends local files to the owner's Kindle library through
Amazon's *Send to Kindle* email service.

```bash
s2k book.epub paper.pdf notes.docx
```

**Success:** each file given on the command line arrives in the Kindle library, or the CLI explains
clearly why a file could not be sent.

### Constraints and context

- Amazon offers no public API for this. The supported programmatic route is an email with the file
  attached, sent to the user's `@kindle.com` address from a sender on the account's *Approved
  Personal Document E-mail List*.
- Single user (the repository owner). No multi-user or multi-device configuration.
- Code lives in `cli/`, managed with Poetry, Python 3.13, virtualenv inside `cli/.venv`.
- All code, docs and git artifacts in English; git usage follows the `git-workflow` skill.

### Out of scope (for now)

URLs/web articles, format conversion, ZIP packing, watch folders/automation, multiple Kindle
addresses, `--dry-run` or other extra flags, packaging/publishing to PyPI.

## 2. Amazon limits (verified 2026-10-05)

Source: Amazon help pages *Send to Kindle Email Address Service* and *Send PDF, EPUB and Other Files
to Your Kindle*.

| Limit | Value |
|---|---|
| Supported extensions | `.doc .docx .html .htm .rtf .txt .jpeg .jpg .gif .png .bmp .pdf .epub` |
| Max total size per email | 50 MB |
| Max attachments per email | 25 (irrelevant here: one file per email) |

MOBI is no longer accepted and is therefore rejected locally.

**Provider limits are stricter in practice.** Gmail caps messages at 25 MB, and base64 encoding
inflates attachments by ~33 %, so with Gmail files above roughly 18 MB will be rejected by the SMTP
server. `s2k` validates against Amazon's 50 MB limit; anything the provider rejects is reported
per file as a send error with the server's message (see §6).

## 3. Technology

| Concern | Choice | Reason |
|---|---|---|
| CLI framework | Typer | Type-hint based arguments, generated help, Rich output |
| Configuration | pydantic-settings (+ `pydantic[email]` for `EmailStr`) | Loads `.env`, validates types and formats at startup |
| Email | stdlib `smtplib` + `email.message.EmailMessage` | No dependency needed |
| Tests | pytest + `typer.testing.CliRunner` | Fake SMTP server; no real emails in tests |
| Lint / format | ruff | Single fast tool |
| Typing | mypy `--strict` | Catch errors early |

Python constraint: `>=3.13,<4.0`. Poetry 2 with a PEP 621 `[project]` table.

## 4. Structure and components

```
cli/
├── pyproject.toml          # deps, tool config (ruff, mypy, pytest), script: s2k = "send_2_kindle.main:app"
├── poetry.toml             # [virtualenvs] in-project = true → cli/.venv
├── poetry.lock
├── .env.example            # versioned template, no real values
├── .env                    # real credentials (git-ignored)
├── README.md               # setup (app password, approved sender), usage, manual smoke test
├── src/send_2_kindle/
│   ├── __init__.py
│   ├── __main__.py         # python -m send_2_kindle
│   ├── constants.py
│   ├── errors.py
│   ├── config.py
│   ├── validation.py
│   ├── mailer.py
│   └── main.py
└── tests/
    ├── conftest.py         # shared fixtures: settings, fake SMTP
    ├── test_validation.py
    ├── test_config.py
    ├── test_mailer.py
    └── test_main.py
```

| Module | Responsibility | Depends on |
|---|---|---|
| `constants.py` | `ALLOWED_EXTENSIONS: frozenset[str]` (lowercase, with dot), `MAX_EMAIL_SIZE_BYTES = 50_000_000` (decimal MB, the conservative reading of "50 MB"), `SMTP_TIMEOUT_SECONDS = 30` | — |
| `errors.py` | Exception hierarchy (§6) | — |
| `config.py` | `Settings` model and `load_settings() -> Settings` | pydantic-settings, `errors` |
| `validation.py` | `validate_file(path: Path) -> None`, raises `FileValidationError` | `constants`, `errors` |
| `mailer.py` | `build_message(settings, path) -> EmailMessage`; `KindleMailer` context manager: connect + login on enter, `send(path)`, quit on exit | `smtplib`, `config`, `errors` |
| `main.py` | Typer app: parse args, orchestrate, print results and summary, exit code | all of the above |

Root `.gitignore` additions: `.venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`.

## 5. Configuration

Variables use the `S2K_` prefix to avoid clashing with other tools' environment variables.

| Variable | Required | Default | Validation |
|---|---|---|---|
| `S2K_KINDLE_EMAIL` | yes | — | `EmailStr` |
| `S2K_SENDER_EMAIL` | yes | — | `EmailStr` |
| `S2K_SMTP_PASSWORD` | yes | — | `SecretStr`, non-empty |
| `S2K_SMTP_HOST` | no | `smtp.gmail.com` | non-empty |
| `S2K_SMTP_PORT` | no | `587` | int, 1–65535 |
| `S2K_SMTP_SECURITY` | no | `starttls` | `starttls` \| `ssl` |
| `S2K_SMTP_USERNAME` | no | value of `S2K_SENDER_EMAIL` | unset or empty → falls back to the sender |

- The `.env` file is resolved at a fixed path, `cli/.env`, computed from the package location
  (`Path(__file__).resolve().parents[2] / ".env"`), so `s2k` works from any working directory.
- Real environment variables take precedence over the `.env` file (pydantic-settings default).
- A missing `.env` file is not an error by itself; missing required variables are.
- `S2K_SMTP_SECURITY` is explicit rather than inferred from the port, to avoid surprises with
  non-Gmail providers.

## 6. Errors

```
S2KError                    base class
├── ConfigError             invalid or incomplete configuration      → exit 2, nothing sent
├── FileValidationError     not found / not a file / extension / size → ✗ for that file, others continue
├── SmtpConnectionError     unreachable host, timeout, TLS failure    → abort run
├── SmtpAuthError           credentials rejected                      → abort run
└── SendError               server rejects one message                → ✗ for that file, others continue
```

Mapping from library errors:

| Source | Raised as |
|---|---|
| `pydantic.ValidationError` while loading settings | `ConfigError` listing each failing variable by its env name (never its value) |
| `OSError`, `socket.timeout`, `ssl.SSLError`, `smtplib.SMTPConnectError`, `SMTPServerDisconnected` during connect/TLS | `SmtpConnectionError` |
| `smtplib.SMTPAuthenticationError` | `SmtpAuthError`; if the host is `smtp.gmail.com`, the message adds the app-password hint and URL `https://myaccount.google.com/apppasswords` |
| `SMTPRecipientsRefused`, `SMTPSenderRefused`, `SMTPDataError` during `send` | `SendError` with the server's code and message |
| `SMTPServerDisconnected` during `send` | `SmtpConnectionError` (abort; remaining files reported as not sent) |

Rules:
- Expected errors print a one-line, actionable message; no traceback.
- Typer is created with `pretty_exceptions_show_locals=False` so an unexpected traceback can never
  print the password from local variables.
- The password is never logged or printed; `SecretStr` masks it in reprs.

## 7. Data flow

```
s2k a.epub b.pdf
 1. Typer parses arguments            → list[Path], at least one required
 2. load_settings()                   → ConfigError: print variables, exit 2
 3. validate_file() for every path    → invalid ones recorded as ✗ with reason
 4. no valid files?                   → print summary, exit 1 (no SMTP connection)
 5. with KindleMailer(settings):      → connect (timeout 30 s), STARTTLS or SSL, login
                                         SmtpConnectionError / SmtpAuthError: print, mark pending as not sent, exit 1
 6.   for each valid file: send()     → ✓ or ✗ (SendError reason)
 7. print summary
 8. exit 0 if every file was sent, else 1
```

Message format: `From` = sender, `To` = Kindle address, `Subject` = file name, empty text body,
one attachment with MIME type from `mimetypes.guess_type` (fallback `application/octet-stream`)
and the original file name.

Example output:
```
✓ a.epub   sent
✗ b.pdf    file exceeds 50 MB (62.3 MB)
1 sent, 1 failed
Note: Amazon may still reject a sent file (e.g. sender not approved); it will email you if so.
```

## 8. Testing

TDD: each behaviour starts with a failing test. Tests never open a real network connection; a fake
SMTP class replaces `smtplib.SMTP` / `smtplib.SMTP_SSL` via `monkeypatch` and records calls.

| File | Covers |
|---|---|
| `test_validation.py` | each allowed extension; case-insensitivity (`.PDF`); disallowed (`.mobi`, no extension); missing path; directory; exactly-at-limit and over-limit size (limit monkeypatched to keep files small) |
| `test_config.py` | required variables missing → `ConfigError` naming them; defaults; username fallback; invalid email / port / security; env vars override `.env`; password masked in `repr` |
| `test_mailer.py` | message headers, subject, attachment bytes, MIME type and fallback; STARTTLS vs SSL class selection; login with username; each library error mapped per §6 |
| `test_main.py` | exit codes 0 / 1 / 2; summary text; no connection when no valid file; abort and "not sent" reporting on auth failure; mixed success/failure |

Quality gates (local and CI): `ruff check`, `ruff format --check`, `mypy --strict src tests`, `pytest`.

Manual smoke test (documented in README, run once by the owner): send a small `.txt` with real
credentials and confirm it appears in the Kindle library.

## 9. CI

New workflow `.github/workflows/cli.yml`, job name **`cli`**:

- Trigger: `pull_request` targeting `main` (all PRs, **no `paths` filter**: a required check that
  never reports would block PRs that don't touch `cli/`). The job first detects whether
  `cli/**` or the workflow changed (`git diff` against the base); if not, it exits successfully
  without running the suite.
- Steps: checkout → setup Python 3.13 → install Poetry → `poetry install` (in `cli/`, with cache) →
  ruff check → ruff format --check → mypy → pytest.
- Third-party actions pinned to full commit SHAs; `permissions: contents: read`.
- After the workflow is merged, `cli` is added to the required status checks of the
  `git-workflow: main` ruleset (alongside `conventions`).

## 10. Open risks

- **Amazon behaviour can change** (formats, limits). Constants are centralized in `constants.py`
  to make updates a one-line change.
- **Delivery is asynchronous.** SMTP acceptance does not guarantee delivery; the CLI states this
  instead of implying success.
