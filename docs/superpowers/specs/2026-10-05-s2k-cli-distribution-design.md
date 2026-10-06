# s2k CLI distribution — Design

- **Date:** 2026-10-05
- **Status:** Draft, pending review
- **Branch:** `feat/cli-distribution`
- **Builds on:** `docs/superpowers/specs/2026-10-05-s2k-cli-design.md` (v0 CLI, merged in #3/#4)

## 1. Goal

Make `s2k` installable and usable by anyone, as the foundation for a Claude Code plugin whose
skills teach agents to set up and use it (sub-project 2, separate spec).

Success:
- Any user can run `pipx install send-2-kindle` (or `uv tool install send-2-kindle`), then
  `s2k init` to configure it, `s2k doctor` to confirm it is ready, and `s2k send FILE...`.
- An agent can tell, from `s2k --version` and `s2k doctor` (exit code + text), whether the CLI is
  installed, configured and able to log in — without ever seeing the user's password.
- Pushing a tag `vX.Y.Z` publishes that version to PyPI and creates a GitHub Release, with no
  stored secrets.

### Out of scope

The plugin and its skills (sub-project 2); JSON output; Windows-specific paths; TestPyPI;
multiple Kindle accounts beyond what `S2K_CONFIG_FILE` already allows.

## 2. Decisions taken during brainstorming

| Topic | Decision |
|---|---|
| Where the plugin is used | Any directory, by any user → CLI must be globally installable and configured per user |
| Organization | Two cycles: this spec (CLI distribution) first, plugin second |
| Readiness / setup | New commands `s2k doctor` and `s2k init`; CLI moves to subcommands |
| Publishing | Tag-triggered GitHub Actions with PyPI Trusted Publishing (OIDC) |
| Versioning | One version for the whole repo, tags `vX.Y.Z` (as in the `git-workflow` skill) |
| License | MIT |
| Agent and secrets | The agent never asks for, reads or writes the SMTP password |

## 3. Commands

```
s2k send FILE...   # unchanged behaviour of today's `s2k FILE...`: one email per file, report, exit codes 0/1/2
s2k doctor         # readiness checks, never sends email (§5)
s2k init           # interactive configuration wizard, run by the user (§6)
s2k --version      # prints "s2k <version>" and exits 0
```

- `s2k` with no subcommand prints the help listing `send`, `doctor` and `init`
  (Typer `no_args_is_help=True`); its exit code is whatever Typer uses for that case.
- Breaking change from v0 (`s2k FILE...` no longer works). Accepted: nothing has been published.
- Exit codes keep their meaning across commands: `0` success, `1` the operation ran and something
  failed, `2` configuration or usage error.

## 4. Configuration resolution

Settings are read, highest priority first, from:

1. Environment variables `S2K_*`.
2. The file named by `S2K_CONFIG_FILE`, if that variable is set (tests, CI, alternative accounts).
3. `$XDG_CONFIG_HOME/s2k/config.env`, defaulting to `~/.config/s2k/config.env`.

- `cli/.env` support is **removed** (its path is meaningless once installed from PyPI). The owner
  migrates with `mkdir -p ~/.config/s2k && mv cli/.env ~/.config/s2k/config.env`.
- `cli/.env.example` is removed; the README documents every variable and `s2k init` writes the file.
- Variables, defaults and validation are unchanged from the v0 spec (§5 there).
- `config.py` exposes `config_file_path() -> Path` (the file that would be read, whether or not it
  exists) so `doctor` and `init` report and write the same path that `load_settings()` reads.
- `S2K_CONFIG_FILE` itself is not a setting and is not written into the file.

## 5. `s2k doctor`

Runs checks in order. A check whose prerequisite failed is shown as skipped (`-`), not as a
cascade of errors.

| # | Check | ✓ | ✗ / ⚠ and the hint printed |
|---|---|---|---|
| 1 | Version | `s2k <version> (Python <x.y.z>)` | — (always ✓) |
| 2 | Config file | path exists | ✗ when the file is missing **and** required variables are not all set in the environment: "No configuration found at <path> → run `s2k init` in your terminal". When it is missing but env vars are set: ✓ "Using environment variables" |
| 3 | File permissions | not readable by group/others | ⚠ (does not fail): "chmod 600 <path>" — skipped on platforms without POSIX modes |
| 4 | Settings | valid; prints `sender <a> → kindle <b>` | ✗ with the same per-variable messages as `ConfigError` (never values) |
| 5 | SMTP connection + TLS | `Connected to <host>:<port> (<STARTTLS\|SSL>)` | ✗ with the `SmtpConnectionError` message |
| 6 | SMTP login | `Logged in as <username>` | ✗ with the `SmtpAuthError` message (Gmail app-password hint) |
| 7 | Amazon (info) | ℹ "Amazon cannot be checked without sending. To confirm end to end: `s2k send <small-file.txt>`" | — |

- Final line `Ready.` when there is no ✗, otherwise `Not ready: <n> problem(s).`
- Exit `0` when there is no ✗ (⚠ allowed), `1` otherwise. Doctor never exits 2: configuration
  problems are findings, not usage errors.
- Checks 5–6 reuse `KindleMailer` (connect + login, then quit) — no second SMTP code path.
  `KindleMailer.__enter__` keeps doing connect, TLS and login together; doctor reports one ✗ on
  whichever step raised (connection errors → check 5, auth errors → check 6 with 5 shown ✓).
- Never sends an email; never prints the password.

## 6. `s2k init`

Interactive wizard; writes the config file returned by `config_file_path()`.

- **Requires an interactive terminal.** If stdin is not a TTY: print "s2k init is interactive; run
  it in your own terminal" and exit 2 — so an agent that runs it by mistake fails fast instead of
  hanging.
- Prompts, in order (defaults in brackets; with an existing valid file its values are the defaults):
  1. Send to Kindle address — hint: Amazon → Manage Your Content and Devices → Preferences →
     Personal Document Settings.
  2. Sender email — hint: must be on the *Approved Personal Document E-mail List*.
  3. SMTP host [`smtp.gmail.com`].
  4. SMTP port [`587`].
  5. Security `starttls|ssl` [`starttls`].
  6. SMTP password — hidden input; hint with the Gmail app-password URL. With an existing file,
     empty input keeps the current password.
- Each answer is validated with the same rules as `Settings`; an invalid answer re-prompts that
  field only, with the validation message.
- `S2K_SMTP_USERNAME` is not prompted (rare); it is preserved if already present in the file.
- Writing: parent directory created with mode `700`; file written atomically (temp file in the same
  directory + `os.replace`) with mode `600`; values quoted so spaces in app passwords survive.
- Then prints `Saved <path> (permissions 600)` and asks `Run checks now? [Y/n]`; yes runs exactly
  the doctor checks and uses doctor's exit code.
- Ctrl-C / EOF at any prompt: nothing is written, exit 1 with "Aborted; configuration not changed."

## 7. Packaging

- PyPI distribution name `send-2-kindle` (verified free on 2026-10-05); script `s2k`.
- `pyproject.toml` metadata: `license = "MIT"`, `license-files = ["LICENSE"]`, `readme =
  "README.md"`, `keywords`, `classifiers` (Python 3.13, OS Independent, Environment :: Console,
  Topic :: Communications :: Email), `[project.urls]` Homepage/Repository/Issues.
- `LICENSE` (MIT, "Copyright (c) 2026 Marco Fura") at the repo root and copied as `cli/LICENSE`
  so the sdist/wheel include it (Poetry packages files under `cli/` only).
- Single version source: `pyproject.toml`. `s2k --version` reads
  `importlib.metadata.version("send-2-kindle")`; the hard-coded `__version__` is removed.
- `cli/README.md` becomes the PyPI page, written for end users: install, `s2k init`, `s2k doctor`,
  `s2k send`, configuration reference, troubleshooting. Development notes move to
  `cli/CONTRIBUTING.md`.

## 8. Release workflow

New `.github/workflows/release.yml`, triggered by `push` of tags `v*`:

| Job | Does | Needs |
|---|---|---|
| `verify` | Tag (minus `v`) equals `pyproject.toml` version under PEP 440 normalization (`v0.2.0-rc.1` ≡ `0.2.0rc1`); tagged commit is reachable from `origin/main` | — |
| `test` | ruff check, ruff format --check, mypy, pytest | verify |
| `build` | `poetry build`; install the wheel into a fresh venv; run `s2k --version` and compare; upload `dist/` artifact | test |
| `publish` | `pypa/gh-action-pypi-publish` (pinned SHA) with `id-token: write`, environment `pypi` | build |
| `github-release` | `gh release create <tag> --verify-tag --generate-notes dist/*`, `--prerelease` for tags containing `-` | publish |

- Permissions: workflow default `contents: read`; `publish` adds `id-token: write`;
  `github-release` adds `contents: write`.
- Pre-releases (`-rc.N`) are published to PyPI as pre-releases; `pipx install send-2-kindle`
  ignores them unless asked.
- Third-party actions pinned to full commit SHAs.
- A failure before `publish` publishes nothing. PyPI never accepts the same version twice; a bad
  release is fixed by releasing the next version.

PR CI (`cli.yml`) gains a step after the tests: `poetry build`, install the wheel into a fresh venv,
run `s2k --version` — packaging errors surface in the PR, not at release time.

`docs/releasing.md` documents:
1. One-time setup: PyPI account with 2FA; *Publishing → Add a pending publisher* with project
   `send-2-kindle`, owner `mjfura`, repository `send-2-kindle`, workflow `release.yml`,
   environment `pypi`; GitHub environment `pypi` (created by the implementation via `gh api`).
2. Each release: release PR bumping the version (`chore(release): vX.Y.Z`), merge, annotated tag
   on `main`, push the tag, watch the workflow.

## 9. Code changes

| File | Change |
|---|---|
| `config.py` | Remove `PROJECT_DIR`/`ENV_FILE`; add `config_file_path()` (§4); `load_settings()` reads that path |
| `main.py` | Typer app with subcommands `send` (current logic), `doctor`, `init`; `--version` callback; `no_args_is_help=True` |
| `doctor.py` (new) | Check runner returning a list of results + rendering; used by `doctor` and by `init` |
| `init.py` (new) | Prompt loop, validation per field, atomic `write_config(path, values)` |
| `__init__.py` | Drop `__version__` |
| `tests/conftest.py` | Isolation now sets `S2K_CONFIG_FILE` to a temp path and clears `XDG_CONFIG_HOME` |
| `cli/.env.example` | Deleted |
| `CLAUDE.md`, `cli/README.md`, `cli/CONTRIBUTING.md` | Updated / created per §7 |

## 10. Testing

TDD as in v0; never real network, never the real user config.

| Area | Tests |
|---|---|
| Config resolution | env > `S2K_CONFIG_FILE` > XDG > `~/.config` default; `config_file_path()` honours each; old `cli/.env` no longer read |
| `send` | Existing CLI tests moved to `s2k send ...`; `s2k` with no args shows help listing `send`, `doctor`, `init` |
| `--version` | Prints the installed distribution version |
| `doctor` | All ✓ → exit 0 and `Ready.`; missing config → ✗ with `s2k init` hint and later checks skipped; env-only config → ✓; permissive file → ⚠ but exit 0; invalid values → ✗ without echoing values; connection failure → ✗ on check 5, check 6 skipped; auth failure → ✓5, ✗6 with Gmail hint; never calls `send_message`; password never in output |
| `init` | Non-TTY → exit 2, nothing written; happy path writes file with mode 600 in dir 700 and values readable by `load_settings()` (including a password with spaces); invalid email re-prompts; existing file: defaults offered, empty password keeps old one, `S2K_SMTP_USERNAME` preserved; Ctrl-C → nothing written, exit 1; "Run checks now? n" → exit 0 without SMTP |
| Packaging | CI builds the wheel, installs it in a clean venv, runs `s2k --version` |

The release workflow itself is verified on the first real release (`v0.1.0`), preceded by
running `verify`'s version comparison locally.

## 11. Rollout

1. Merge this work (version stays `0.1.0`).
2. Owner completes the one-time PyPI setup (`docs/releasing.md`).
3. Tag `v0.1.0` on `main` → first publication.
4. Smoke test from a clean environment: `pipx install send-2-kindle`, `s2k doctor`, `s2k send`.
5. Start sub-project 2 (plugin) against the published CLI.
