# Choosing the format

| Content | basic (6–7") | scribe | colorsoft | app |
|---|---|---|---|---|
| Text: plans, specs, notes, reports, Markdown, plain text | EPUB | EPUB | EPUB | EPUB |
| Fixed layout: papers, slides, comics, forms | PDF (warn: small text) | PDF | PDF | PDF |
| EPUB, DOCX, images | as is | as is | as is | as is |

- EPUB reflows to the screen and the reader's font size: recommend it for anything that is mostly text.
- Keep a PDF as PDF when its layout matters; on 6–7" screens warn that text will be small.
- Color only helps on `colorsoft` and `app`; otherwise do not rely on color to carry meaning.

## Conversions

| From | To | How |
|---|---|---|
| Markdown, plain text, HTML, content you write | EPUB | Write HTML chapters ([reading-editions.md](reading-editions.md)) and run `make_epub.py` |
| `.mobi`, `.azw3` | EPUB | `ebook-convert <in> "${TMPDIR:-/tmp}/s2k/<name>.epub"` (Calibre). If `command -v ebook-convert` fails, propose installing Calibre (macOS: `brew install --cask calibre`) and wait for a yes. Never send the original |
| PDF over the size limit | smaller PDF | `gs -sDEVICE=pdfwrite -dPDFSETTINGS=/ebook -o "${TMPDIR:-/tmp}/s2k/<name>.pdf" <in>` if Ghostscript is installed; otherwise explain the limit |
| DOCX | as is | Amazon converts it; build a reading edition only if the user asks |

Limits: 50 MB per file; Gmail refuses messages above about 25 MB, so files above ~18 MB fail with Gmail.
