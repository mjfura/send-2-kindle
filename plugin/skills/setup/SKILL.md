---
name: setup
description: Install, configure, verify or troubleshoot the s2k CLI that emails documents to a Kindle (Amazon Send to Kindle). Use it whenever the user wants to set up sending to their Kindle, asks whether s2k is ready, shares an s2k error ("command not found", "No configuration found", "authentication failed", "could not connect"), or when sending to a Kindle fails because s2k is missing, outdated or not configured.
allowed-tools:
  - Bash(s2k --version)
  - Bash(s2k doctor)
---

# Set up s2k

`s2k` (PyPI package `s2k-cli`, Python 3.13+) emails files to the user's Kindle. It is ready when the
CLI is installed (0.1.0 or newer), the **user** has configured it with `s2k init`, and
`s2k doctor` ends with `Ready.`

## Never handle the SMTP password

- Never ask for the email password (for Gmail, the *app password*), and never put it in a command,
  file or message.
- Never run `s2k init` yourself: it is an interactive wizard the user runs in **their own
  terminal** — not with Claude Code's `!` prefix, which cannot answer its prompts.
- Never read or edit the config file (`~/.config/s2k/config.env` or `$S2K_CONFIG_FILE`); use
  `s2k doctor`.
- If the user pastes a password anyway: do not repeat or use it. Ask them to run `s2k init`
  themselves and to revoke that app password and create a new one, because it is now stored in
  this conversation.

## 1. Installed and recent enough?

Run `s2k --version`.
- **Command not found:** check `command -v pipx` and `command -v uv`. Propose `pipx install s2k-cli`
  (or `uv tool install s2k-cli`) and run it only after the user agrees. If the default Python is
  older than 3.13, use `pipx install --python python3.13 s2k-cli`. Without pipx or uv, point to
  https://pipx.pypa.io/stable/installation/.
- **Older than 0.1.0:** propose `pipx upgrade s2k-cli` (or `uv tool upgrade s2k-cli`), same consent rule.

## 2. Configured and able to log in?

Run `s2k doctor` (never sends email; exit 0 = ready, 1 = at least one ✗).

| `s2k doctor` shows | What to do |
|---|---|
| ✗ No configuration found … run `s2k init` | Check the prerequisites below with the user, ask them to run `s2k init` in their own terminal and to tell you when it is done |
| ✗ authentication failed … | Gmail needs an app password, not the account password: https://myaccount.google.com/apppasswords (2-Step Verification required); then `s2k init` again |
| ✗ could not connect … / does not support a required feature | Wrong server, port or security: `s2k init` again (Gmail: `smtp.gmail.com`, `587`, `starttls`; port 465 needs `ssl`) |
| ✗ Invalid configuration … `S2K_…` | `s2k init` again, correcting that value |
| ✗ Cannot read … | Fix that file's owner or permissions (`ls -l <path>`) |
| ⚠ Config file is readable by other users | You may run the `chmod 600 <path>` it prints |
| ℹ Amazon cannot be checked … | Expected; see step 4 |

Prerequisites for `s2k init`:
1. The Send to Kindle address: Amazon → *Manage Your Content and Devices* → *Preferences* →
   *Personal Document Settings*.
2. The sender email added to the *Approved Personal Document E-mail List* on that page.
3. For Gmail, an app password (link above).

## 3. Repeat `s2k doctor` until it ends with `Ready.`

## 4. Optional end-to-end test

Only if the user agrees (it sends a real email): create a small text file and run `s2k send <file>`.
Amazon delivers within minutes; if it rejects the document (for example, the sender is not
approved), Amazon emails the user.
