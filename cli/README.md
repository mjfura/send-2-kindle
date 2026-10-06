# s2k — send files to your Kindle

`s2k` emails local files to your Kindle using Amazon's Send to Kindle service, one email per file.

```bash
s2k book.epub paper.pdf notes.docx
```

Supported: `.pdf .epub .doc .docx .txt .rtf .html .htm .jpg .jpeg .png .gif .bmp`, up to 50 MB
each (your email provider may allow less: Gmail rejects files above roughly 18 MB).

## Setup

1. **Find your Kindle address and approve your sender.** In Amazon, go to *Manage Your Content and
   Devices → Preferences → Personal Document Settings*. Copy your `@kindle.com` address and add the
   email you will send from to the *Approved Personal Document E-mail List*.
2. **Gmail only: create an app password.** It requires 2-Step Verification:
   <https://myaccount.google.com/apppasswords>. Other providers: use your SMTP credentials and set
   `S2K_SMTP_HOST`, `S2K_SMTP_PORT` and `S2K_SMTP_SECURITY`.
3. **Install** (Python 3.13 and Poetry 2 required):
   ```bash
   cd cli
   poetry env use python3.13
   poetry install
   ```
4. **Configure:** `cp .env.example .env` and fill in the values. `cli/.env` is git-ignored.

## Usage

```bash
poetry run s2k FILE...          # from cli/
source cli/.venv/bin/activate   # or activate once and run `s2k` from anywhere
```

Exit codes: `0` every file was sent · `1` at least one file was not sent · `2` invalid
configuration or usage.

"Sent" means your SMTP server accepted the email. If Amazon rejects it (for example, the sender is
not approved), Amazon emails you.

## Development

```bash
cd cli
poetry run pytest                 # tests (never send real email)
poetry run ruff check .           # lint
poetry run ruff format .          # format
poetry run mypy src tests         # type check
```

### Manual smoke test

With a real `cli/.env`:
```bash
echo "s2k smoke test" > /tmp/s2k-smoke.txt
poetry run s2k /tmp/s2k-smoke.txt
```
The document should appear in your Kindle library within a few minutes.
