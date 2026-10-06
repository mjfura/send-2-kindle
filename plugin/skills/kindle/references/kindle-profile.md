# Kindle profile

Saved preferences so you only ask per-document questions next time.

- **Path:** `${XDG_CONFIG_HOME:-$HOME/.config}/s2k/reading.json` (same folder as the s2k config;
  it never contains secrets).
- **Format:**
  ```json
  { "kindle": "basic", "author": "Ada Lovelace", "cover": true, "language": "en" }
  ```
  `kindle`: `basic` (Kindle or Paperwhite, 6–7" black-and-white), `scribe` (10.2"), `colorsoft`
  (color e-ink), `app` (phone, tablet or computer), `other`.

## First-time questions (ask together with the document questions)

1. Which Kindle will you read on? — Kindle/Paperwhite · Scribe · Colorsoft · Kindle app
2. Default author for documents I create for you? — offer the git `user.name` if available · other
3. Add a cover page by default? — Yes, a simple text cover · No
4. Language of the documents? — offer the language of the conversation · other

Then ask: "Save these as your defaults in `reading.json`?" Write the file only after a yes
(create the folder if needed). When the user asks to change a default, update only that key.
