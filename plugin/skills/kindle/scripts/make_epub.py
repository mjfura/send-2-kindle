#!/usr/bin/env python3
"""Package HTML chapter fragments into an EPUB 3 for Kindle (Python standard library only).

Usage:
  python3 make_epub.py --title TITLE --author AUTHOR --output OUT.epub
                       [--date YYYY-MM-DD] [--language en] [--cover] CHAPTER.html [...]

Each CHAPTER.html is an HTML fragment (body content). Its first <h1> becomes the chapter title,
otherwise the file name does. Fragments are sanitized into well-formed XHTML.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import sys
import uuid
import zipfile
from html.parser import HTMLParser
from pathlib import Path

VOID = {"br", "hr", "col", "wbr"}
ALLOWED = {
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "br", "hr", "ul", "ol", "li", "blockquote", "pre",
    "code", "em", "strong", "b", "i", "u", "s", "del", "sub", "sup", "small", "a", "table",
    "thead", "tbody", "tfoot", "tr", "th", "td", "caption", "colgroup", "col", "dl", "dt", "dd",
    "div", "span", "figure", "figcaption", "wbr",
}  # fmt: skip
DROP_WITH_CONTENT = {"script", "style", "head", "title", "iframe", "object", "noscript", "template"}
ALLOWED_ATTRIBUTES = {"a": {"href"}, "td": {"colspan", "rowspan"}, "th": {"colspan", "rowspan"}}
SAFE_LINK_SCHEMES = {"http", "https", "mailto"}

STYLESHEET = """\
body { font-family: serif; line-height: 1.5; margin: 0 0.5em; }
h1 { font-size: 1.6em; margin: 1em 0 0.6em; page-break-before: always; }
h2 { font-size: 1.3em; margin: 1em 0 0.5em; }
h3 { font-size: 1.1em; margin: 0.8em 0 0.4em; }
pre { font-family: monospace; font-size: 0.85em; white-space: pre-wrap; word-wrap: break-word;
      border-left: 3px solid #999; padding-left: 0.5em; }
code { font-family: monospace; font-size: 0.9em; }
table { border-collapse: collapse; width: 100%; font-size: 0.9em; }
th, td { border: 1px solid #666; padding: 0.2em 0.4em; text-align: left; vertical-align: top; }
blockquote { margin: 0.5em 1.5em; font-style: italic; }
.cover { text-align: center; margin-top: 30%; }
.cover h1 { page-break-before: avoid; font-size: 2em; }
.cover .author { font-size: 1.2em; }
.cover .date { color: #555; }
"""


def _escape(text: str) -> str:
    return html.escape(text, quote=False)


def _safe_href(value: str) -> bool:
    """Allow http(s)/mailto links and relative links; reject every other scheme (javascript:, data:…)."""
    # Readers ignore whitespace and control characters inside a scheme ("java\tscript:").
    compact = "".join(char for char in value if char.isprintable() and not char.isspace())
    head = compact.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if ":" not in head:
        return True
    return head.split(":", 1)[0].lower() in SAFE_LINK_SCHEMES


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.stack: list[str] = []
        self.skip_depth = 0
        self.first_h1: str | None = None
        self._h1_text: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in DROP_WITH_CONTENT:
            self.skip_depth += 1
            return
        if self.skip_depth or tag not in ALLOWED:
            return
        kept = ""
        for name, value in attrs:
            if name in ALLOWED_ATTRIBUTES.get(tag, set()) and value:
                if name == "href" and not _safe_href(value):
                    continue
                kept += f' {name}="{html.escape(value, quote=True)}"'
        if tag in VOID:
            self.out.append(f"<{tag}{kept}/>")
            return
        self.out.append(f"<{tag}{kept}>")
        self.stack.append(tag)
        if tag == "h1" and self.first_h1 is None and self._h1_text is None:
            self._h1_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag in DROP_WITH_CONTENT:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth or tag in VOID or tag not in self.stack:
            return
        while self.stack:
            if self._close_top() == tag:
                break

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        self.out.append(_escape(data))
        if self._h1_text is not None:
            self._h1_text.append(data)

    def _close_top(self) -> str:
        tag = self.stack.pop()
        self.out.append(f"</{tag}>")
        if tag == "h1" and self._h1_text is not None:
            self.first_h1 = " ".join("".join(self._h1_text).split()) or None
            self._h1_text = None
        return tag

    def finish(self) -> str:
        self.close()
        while self.stack:
            self._close_top()
        return "".join(self.out)


def sanitize(fragment: str) -> tuple[str, str | None]:
    """Return (well-formed XHTML body, text of the first <h1> or None)."""
    parser = _Sanitizer()
    parser.feed(fragment)
    body = parser.finish()
    return body, parser.first_h1


def _page(title: str, body: str, language: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
        f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" '
        f'xml:lang="{language}" lang="{language}">\n'
        f'<head><meta charset="utf-8"/><title>{_escape(title)}</title>'
        '<link rel="stylesheet" type="text/css" href="style.css"/></head>\n'
        f"<body>\n{body}\n</body>\n</html>\n"
    )


def build_epub(
    output: Path,
    title: str,
    author: str,
    chapters: list[Path],
    *,
    date: str,
    language: str = "en",
    cover: bool = False,
) -> Path:
    """Write an EPUB 3 to ``output`` from HTML fragment files and return its path."""
    book_id = f"urn:uuid:{uuid.uuid4()}"
    modified = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    files: dict[str, str] = {}
    toc: list[tuple[str, str]] = []

    for number, path in enumerate(chapters, start=1):
        body, heading = sanitize(path.read_text(encoding="utf-8"))
        chapter_title = heading or path.stem
        if heading is None:
            body = f"<h1>{_escape(chapter_title)}</h1>\n{body}"
        name = f"chapter-{number:03d}.xhtml"
        files[name] = _page(chapter_title, body, language)
        toc.append((name, chapter_title))

    if cover:
        files["cover.xhtml"] = _page(
            title,
            f'<section epub:type="cover" class="cover"><h1>{_escape(title)}</h1>'
            f'<p class="author">{_escape(author)}</p><p class="date">{_escape(date)}</p></section>',
            language,
        )

    links = "\n".join(f'<li><a href="{name}">{_escape(label)}</a></li>' for name, label in toc)
    files["nav.xhtml"] = _page(
        "Contents", f'<nav epub:type="toc" id="toc"><h1>Contents</h1><ol>\n{links}\n</ol></nav>', language
    )
    points = "\n".join(
        f'<navPoint id="navpoint-{index}" playOrder="{index}"><navLabel><text>{_escape(label)}</text>'
        f'</navLabel><content src="{name}"/></navPoint>'
        for index, (name, label) in enumerate(toc, start=1)
    )
    files["toc.ncx"] = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1"><head>'
        f'<meta name="dtb:uid" content="{book_id}"/><meta name="dtb:depth" content="1"/>'
        '<meta name="dtb:totalPageCount" content="0"/><meta name="dtb:maxPageNumber" content="0"/>'
        f"</head><docTitle><text>{_escape(title)}</text></docTitle><navMap>\n{points}\n</navMap></ncx>\n"
    )
    files["style.css"] = STYLESHEET

    manifest = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '<item id="style" href="style.css" media-type="text/css"/>',
    ]
    spine = ['<itemref idref="nav"/>']
    if cover:
        manifest.append('<item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>')
        spine.insert(0, '<itemref idref="cover"/>')
    for name, _ in toc:
        item_id = name[: -len(".xhtml")]
        manifest.append(f'<item id="{item_id}" href="{name}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="{item_id}"/>')
    files["content.opf"] = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id" '
        f'xml:lang="{language}">\n<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        f'<dc:identifier id="book-id">{book_id}</dc:identifier>\n'
        f"<dc:title>{_escape(title)}</dc:title>\n<dc:creator>{_escape(author)}</dc:creator>\n"
        f"<dc:language>{_escape(language)}</dc:language>\n<dc:date>{_escape(date)}</dc:date>\n"
        f'<meta property="dcterms:modified">{modified}</meta>\n</metadata>\n'
        f"<manifest>\n{chr(10).join(manifest)}\n</manifest>\n"
        f'<spine toc="ncx">\n{chr(10).join(spine)}\n</spine>\n</package>\n'
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
            "</rootfiles></container>\n",
            compress_type=zipfile.ZIP_DEFLATED,
        )
        for name, content in files.items():
            archive.writestr(f"OEBPS/{name}", content, compress_type=zipfile.ZIP_DEFLATED)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an EPUB from HTML chapter fragments.")
    parser.add_argument("--title", required=True)
    parser.add_argument("--author", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--date", default=dt.date.today().isoformat(), help="YYYY-MM-DD")
    parser.add_argument("--language", default="en")
    parser.add_argument("--cover", action="store_true", help="add a text cover page")
    parser.add_argument("chapters", nargs="+", type=Path)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exit_:
        return int(exit_.code or 0)
    try:
        dt.date.fromisoformat(args.date)
    except ValueError:
        print(f"make_epub: invalid --date {args.date!r}; use YYYY-MM-DD", file=sys.stderr)
        return 2
    missing = [str(path) for path in args.chapters if not path.is_file()]
    if missing:
        print(f"make_epub: chapter file not found: {', '.join(missing)}", file=sys.stderr)
        return 2
    try:
        output = build_epub(
            args.output, args.title, args.author, args.chapters,
            date=args.date, language=args.language, cover=args.cover,
        )  # fmt: skip
    except (OSError, UnicodeDecodeError) as error:
        print(f"make_epub: {error}", file=sys.stderr)
        return 2
    print(f"{output} ({output.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
