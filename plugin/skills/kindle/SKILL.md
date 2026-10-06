---
name: kindle
description: Send anything the user wants to read to their Kindle — existing files (books, PDFs, EPUBs, specs, plans, notes, reports) or content you write for them (a project summary, a report, the proposals, the plan from this conversation) — as a pleasant reading edition, using the s2k CLI (Amazon Send to Kindle by email). Use it whenever the user asks to send, mail or put something on their Kindle, wants to read something on their Kindle, or asks for a Kindle-friendly version of a document, even if they do not mention s2k.
allowed-tools:
  - Bash(s2k --version)
  - Bash(s2k doctor)
  - Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/make_epub.py *)
---

# Read it on Kindle

The user wants to *read* something on their Kindle. Find out exactly what and how, build the best
reading edition, show it, then send it with `s2k`.

## Workflow

1. **Understand the request** and classify the source:
   - *Existing file(s)* the user named.
   - *A selection* you must interpret ("all the PDFs in Downloads", "the latest report").
   - *Content to compose*: a summary, a report, the proposals, the plan or spec from this conversation.
2. **Check s2k:** run `s2k --version`. Not found, failing or older than 0.1.0 → follow `s2k:setup` first.
3. **Load the Kindle profile** from `${XDG_CONFIG_HOME:-$HOME/.config}/s2k/reading.json`. If it is
   missing, include the profile questions from [kindle-profile.md](references/kindle-profile.md) in step 4.
4. **Ask only what is still undecided** with `AskUserQuestion` (at most 4 questions per call; ask in
   text if the tool is unavailable). Put your recommendation first with a one-line reason. Skip
   only what the request or the profile already settles — "send ./books/dune.epub as is" needs no
   questions. The profile supplies defaults (Kindle model, author, cover, language); it never
   decides *how* to send a document: unless the user already said it, always ask whether to send an
   existing file as is, as a reading edition or summarized, and in which format — before building
   anything.
   - *Existing file:* how to send it (reading edition · as is · summarized version) · format (EPUB ·
     PDF · original; see [formats.md](references/formats.md)) · title and author · cover (text cover
     page · none).
   - *Content to compose:* scope (short summary · full report · decisions and next steps) · sources
     to use (list what you found: spec, plan, commits, this conversation) · title and author · cover.
   - *Selection:* the exact files with sizes, to confirm or narrow down.
5. **Build** in `${TMPDIR:-/tmp}/s2k/` — never inside the user's project, never modifying originals.
   - EPUB: write one HTML fragment per chapter following
     [reading-editions.md](references/reading-editions.md), then run
     `python3 ${CLAUDE_SKILL_DIR}/scripts/make_epub.py --title "<title>" --author "<author>" [--cover] [--language <code>] --output "${TMPDIR:-/tmp}/s2k/<slug>.epub" <chapter-01.html> <chapter-02.html> …`
   - Other conversions (MOBI/AZW3, oversized PDFs): [formats.md](references/formats.md).
6. **Preview and confirm** anything you created, transformed or selected: title, author, chapter
   list, file name and size. Send only after an explicit yes, unless the user told you not to ask.
7. **Send** everything in one call: `s2k send "<file1>" "<file2>"` — quote every path.
8. **Report** from the exit code and the ✓/✗ lines:
   - 0: sent. Amazon delivers within minutes and emails the user if it rejects a document. Say where
     generated files are.
   - 1: which files failed and why. Authentication or connection errors → `s2k:setup` (start with
     `s2k doctor`). Too large → explain the limit.
   - 2 or command not found → `s2k:setup`.

## Rules

- A reading edition keeps all the content: restructure and format, never drop or invent. Write new
  content (summaries, reports) only when asked.
- Never send anything the user did not name or confirm. Never retry a failed send on your own:
  duplicates land in the library.
- Send to Kindle accepts `.pdf .epub .doc .docx .txt .rtf .html .htm .jpg .jpeg .png .gif .bmp`, up
  to 50 MB per file (Gmail: about 18 MB, iCloud Mail: about 14 MB), not empty. Convert
  `.mobi`/`.azw3` first.
- Files in iCloud Drive that are not downloaded are downloaded automatically when sent (needs a
  connection); warn the user before sending many or large ones.
- Never read the s2k config file or ask for passwords — configuration belongs to `s2k:setup`.
