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
pipx install s2k-cli       # or: uv tool install s2k-cli
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
