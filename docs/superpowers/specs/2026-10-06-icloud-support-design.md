# iCloud support — Design

- **Date:** 2026-10-06
- **Status:** Draft, pending review
- **Branch:** `feat/icloud-support`
- **Builds on:** `2026-10-05-s2k-cli-distribution-design.md`, `2026-10-05-s2k-plugin-design.md` (released as v0.2.0)

## 1. Goal

Make iCloud a first-class way to use s2k:
1. **iCloud Mail as a sender**: picking it in `s2k init` fills the server settings; errors and size
   limits speak iCloud.
2. **Files in iCloud Drive**: files that macOS has not downloaded ("dataless") are downloaded
   automatically when sent, with a clear message, and a clear error when that fails.

Already true today (no change needed): any SMTP server works, so iCloud Mail can be configured by
hand (`smtp.mail.me.com`, 587, STARTTLS, full iCloud address as username, app-specific password).

### Out of scope

Outlook/Hotmail (Microsoft is retiring password-based SMTP for personal accounts); Mail Drop (not
available over SMTP, and Amazon needs the file itself); a provider config variable; iCloud Drive
`.icloud` placeholder files (not used by current macOS — verified on macOS 27: not-downloaded files
are regular paths with the `SF_DATALESS` flag).

## 2. Decisions taken during brainstorming

| Topic | Decision |
|---|---|
| Scope | Provider presets in `init`, provider-specific hints, provider size limits, iCloud Drive downloads |
| Provider identification | Derived from `S2K_SMTP_HOST` (option A); no new variable |
| Not-downloaded iCloud Drive files | Downloaded automatically when sent (option A), validated first |
| Evals | One new case (iCloud auth failure) + the setup cases, run once with owner approval |
| Release | `v0.3.0` after merge, with owner approval |

## 3. Providers

New module `providers.py`:

```python
@dataclass(frozen=True)
class Provider:
    key: str                 # "gmail" | "icloud"
    name: str                # "Gmail" | "iCloud"
    host: str                # "smtp.gmail.com" | "smtp.mail.me.com"
    port: int                # 587
    security: str            # "starttls"
    max_file_bytes: int      # 18_000_000 | 14_000_000
    password_name: str       # "app password" | "app-specific password"
    password_url: str        # https://myaccount.google.com/apppasswords | https://account.apple.com

PROVIDERS: tuple[Provider, ...]
def provider_for_host(host: str) -> Provider | None   # case-insensitive, surrounding spaces ignored
```

- Size limits are conservative: Gmail accepts 25 MB messages and iCloud 20 MB
  ([Apple](https://support.apple.com/en-us/102198)); base64 grows attachments by ~33 %.
- Unknown hosts ("other") keep Amazon's 50 MB limit.
- `constants.GMAIL_SMTP_HOST` and `GMAIL_APP_PASSWORDS_URL` move into the registry (constants keeps
  only non-provider values); `Settings.smtp_host` still defaults to Gmail's host.

## 4. `s2k init`

- New first question: `Email provider (gmail/icloud/other)`. Default: the provider of the existing
  config's host, `other` for an unknown existing host, `gmail` for a new config.
- `gmail`/`icloud`: host, port and security are set from the registry and **not** prompted.
  `other`: the three prompts work as today (defaults from the existing config).
- Sender prompt hint for iCloud: "your iCloud Mail address, e.g. name@icloud.com".
- Password prompt shows the provider's password name and URL (other: plain "SMTP password").
- Intro text mentions Gmail and iCloud passwords.
- Everything else (confirmation, symlinks, permissions, checks at the end) unchanged.

## 5. Messages and validation

- **Auth failures** (`_auth_failure_message`): for a known provider, ". {name} requires an
  {password_name}, not your account password: {password_url}". Unknown host: no hint. Applies to
  `send`, `doctor` and `init`'s checks (they share `KindleMailer`).
- **Size:** `validate_file(path, max_bytes=constants.MAX_EMAIL_SIZE_BYTES, provider_name=None)`.
  `send` passes `min(50 MB, provider.max_file_bytes)` and the provider name, so the reason reads
  `file exceeds 14 MB, the limit for iCloud (16.2 MB)`; without a provider:
  `file exceeds 50 MB (62.3 MB)` (unchanged).
- **iCloud Drive:** `validation.is_not_downloaded(path) -> bool` — true on macOS when
  `os.stat(path).st_flags & SF_DATALESS` (`0x40000000`); false elsewhere or when `st_flags` is
  missing. Validation reads only `stat`, so extension and size are checked before any download.
- **Sending a not-downloaded file:** `main.send` prints `Downloading "<name>" from iCloud…` before
  sending it; reading the file (in `build_message`) makes macOS download it. If that read fails,
  `KindleMailer.send` raises `SendError("could not download it from iCloud (are you offline?): …")`
  instead of the generic "could not read file". Other files keep being sent.

## 6. Plugin

- `s2k:setup`: a providers table (Gmail, iCloud, other) with server settings and where to create the
  password; iCloud prerequisites (2-factor authentication, app-specific password at
  account.apple.com, the iCloud address on Amazon's approved list); the auth row of the doctor table
  covers both providers.
- `s2k:kindle` and `references/formats.md`: limits per provider (Gmail ~18 MB, iCloud ~14 MB);
  iCloud Drive files are downloaded automatically when sent — warn the user before sending many or
  large not-downloaded files.
- Fake CLI: new scenario `auth-fail-icloud` (doctor/send report the iCloud hint).
- New eval case `setup-explains-icloud-auth-failure`; run it with the four `setup-*` cases once
  (owner approval).

## 7. Docs

`cli/README.md` (providers table, iCloud setup, iCloud Drive note, limits), `plugin/README.md`
(iCloud mention), `docs/releasing.md` unchanged.

## 8. Testing

| Area | Tests |
|---|---|
| Registry | `provider_for_host` known/unknown/case/spaces; limits below 50 MB |
| `init` | provider choice fills host/port/security without prompting; `other` prompts; existing iCloud config defaults to `icloud`; unknown host defaults to `other`; password hint shows Apple's URL for iCloud |
| Auth hint | iCloud host → app-specific password + account.apple.com; Gmail unchanged; other host → no hint |
| Size | iCloud config rejects a file above 14 MB with the provider name; Gmail above 18 MB; other host keeps 50 MB |
| iCloud Drive | `is_not_downloaded` true/false via a stubbed `st_flags`; `send` prints the download line for such a file; a read failure on it yields the iCloud error and other files are still sent |
| Fake CLI | `auth-fail-icloud` scenario in `test_stub.sh` |
| Behaviour | Eval run (5 setup cases), owner-approved |

A manual check on the owner's Mac: send one not-downloaded PDF from iCloud Drive with real
credentials (owner-approved), confirming the automatic download.

## 9. Rollout

Merge → (owner) release `v0.3.0` bumping CLI and plugin → users upgrade with `pipx upgrade s2k-cli`
and `/plugin marketplace update send-2-kindle`.
