"""Tests for skills/kindle/scripts/make_epub.py. Run: python3 -m unittest discover -s plugin/tests"""

import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET  # parses only XML this test suite generated itself
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "kindle" / "scripts"))

import make_epub  # noqa: E402

NS = {
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "x": "http://www.w3.org/1999/xhtml",
    "ncx": "http://www.daisy.org/z3986/2005/ncx/",
}


class MakeEpubTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())

    def _chapter(self, name: str, html: str) -> Path:
        path = self.dir / name
        path.write_text(html, encoding="utf-8")
        return path

    def _build(self, chapters: list[Path], **kwargs: object) -> zipfile.ZipFile:
        output = self.dir / "out" / "book.epub"
        options = {"date": "2026-10-05", "language": "en", "cover": False}
        options.update(kwargs)
        make_epub.build_epub(output, "Project Plan", "Test Reader", chapters, **options)
        return zipfile.ZipFile(output)

    def _two_chapters(self) -> list[Path]:
        return [
            self._chapter("01.html", "<h1>Overview</h1><p>Goal.</p>"),
            self._chapter("02.html", "<h1>Tasks</h1><ul><li>One</li></ul>"),
        ]

    def test_builds_a_valid_epub_container(self) -> None:
        book = self._build(self._two_chapters())
        first = book.infolist()[0]
        self.assertEqual(first.filename, "mimetype")
        self.assertEqual(first.compress_type, zipfile.ZIP_STORED)
        self.assertEqual(book.read("mimetype"), b"application/epub+zip")
        container = ET.fromstring(book.read("META-INF/container.xml"))
        rootfile = container.find(".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile")
        self.assertIsNotNone(rootfile)
        self.assertEqual(rootfile.get("full-path"), "OEBPS/content.opf")
        for name in ("OEBPS/nav.xhtml", "OEBPS/toc.ncx", "OEBPS/style.css",
                     "OEBPS/chapter-001.xhtml", "OEBPS/chapter-002.xhtml"):
            self.assertIn(name, book.namelist())

    def test_opf_has_metadata_and_reading_order(self) -> None:
        book = self._build(self._two_chapters(), language="es")
        opf = ET.fromstring(book.read("OEBPS/content.opf"))
        self.assertEqual(opf.findtext(".//dc:title", namespaces=NS), "Project Plan")
        self.assertEqual(opf.findtext(".//dc:creator", namespaces=NS), "Test Reader")
        self.assertEqual(opf.findtext(".//dc:language", namespaces=NS), "es")
        self.assertEqual(opf.findtext(".//dc:date", namespaces=NS), "2026-10-05")
        self.assertTrue(opf.findtext(".//dc:identifier", namespaces=NS).startswith("urn:uuid:"))
        modified = [m for m in opf.iterfind(".//opf:meta", NS) if m.get("property") == "dcterms:modified"]
        self.assertEqual(len(modified), 1)
        spine = [ref.get("idref") for ref in opf.iterfind(".//opf:spine/opf:itemref", NS)]
        self.assertEqual(spine, ["nav", "chapter-001", "chapter-002"])

    def test_table_of_contents_lists_each_chapter_title(self) -> None:
        book = self._build(self._two_chapters())
        nav = ET.fromstring(book.read("OEBPS/nav.xhtml"))
        titles = [a.text for a in nav.iterfind(".//x:nav//x:a", NS)]
        self.assertEqual(titles, ["Overview", "Tasks"])
        ncx = ET.fromstring(book.read("OEBPS/toc.ncx"))
        labels = [t.text for t in ncx.iterfind(".//ncx:navPoint/ncx:navLabel/ncx:text", NS)]
        self.assertEqual(labels, ["Overview", "Tasks"])

    def test_chapter_without_h1_uses_the_file_name(self) -> None:
        book = self._build([self._chapter("next-steps.html", "<p>Ship it.</p>")])
        chapter = book.read("OEBPS/chapter-001.xhtml").decode()
        self.assertIn("<h1>next-steps</h1>", chapter)

    def test_malformed_html_is_repaired(self) -> None:
        html = "<h1>Plan</h1><p>unclosed <b>bold<li>item<br> 1 < 2 &nbsp;&amp; done</div>"
        book = self._build([self._chapter("bad.html", html)])
        ET.fromstring(book.read("OEBPS/chapter-001.xhtml"))  # raises if not well-formed

    def test_active_content_is_dropped(self) -> None:
        html = (
            "<h1>T</h1><script>alert(1)</script><style>p{}</style>"
            "<p onclick=\"evil()\">text</p><a href=\"javascript:evil()\">link</a>"
            "<a href=\"https://example.com\">ok</a>"
        )
        chapter = self._build([self._chapter("a.html", html)]).read("OEBPS/chapter-001.xhtml").decode()
        for forbidden in ("script", "alert", "onclick", "javascript:", "p{}"):
            self.assertNotIn(forbidden, chapter)
        self.assertIn('href="https://example.com"', chapter)

    def test_only_safe_link_schemes_are_kept(self) -> None:
        hrefs = [
            "java\tscript:evil()", "java\nscript:evil()", " JAVASCRIPT:evil()",
            "vbscript:evil()", "data:text/html,evil", "&#106;avascript:evil()",
        ]
        html = "<h1>T</h1>" + "".join(f'<a href="{h}">bad</a>' for h in hrefs)
        html += '<a href="https://ok.example">a</a><a href="mailto:me@example.com">b</a><a href="#part">c</a>'
        chapter = self._build([self._chapter("l.html", html)]).read("OEBPS/chapter-001.xhtml").decode()
        for forbidden in ("script:", "evil", "data:"):
            self.assertNotIn(forbidden, chapter)
        for kept in ('href="https://ok.example"', 'href="mailto:me@example.com"', 'href="#part"'):
            self.assertIn(kept, chapter)

    def test_control_characters_are_removed(self) -> None:
        html = '<h1>T\x01</h1><p>a\x00b\x0bc\x0cd\x1be</p><a href="https://ok.example/\x01x">l</a>'
        output = self.dir / "ctl.epub"
        make_epub.build_epub(output, "Ti\x02tle", "Au\x1bthor", [self._chapter("c.html", html)], date="2026-10-05")
        book = zipfile.ZipFile(output)
        for name in book.namelist():
            if name.endswith((".xhtml", ".opf", ".ncx")):
                ET.fromstring(book.read(name))
        chapter = book.read("OEBPS/chapter-001.xhtml").decode()
        self.assertIn("abcde", chapter)

    def test_unclosed_iframe_does_not_swallow_the_rest(self) -> None:
        html = "<h1>T</h1><iframe src=x>fallback<p>rest of the book</p>"
        chapter = self._build([self._chapter("i.html", html)]).read("OEBPS/chapter-001.xhtml").decode()
        self.assertIn("rest of the book", chapter)

    def test_document_with_unclosed_head_keeps_its_body(self) -> None:
        html = "<head><meta charset=utf-8><body><h1>Real chapter</h1><p>Body text</p>"
        chapter = self._build([self._chapter("h.html", html)]).read("OEBPS/chapter-001.xhtml").decode()
        self.assertIn("Body text", chapter)
        self.assertIn("<h1>Real chapter</h1>", chapter)

    def test_output_must_be_an_epub_path(self) -> None:
        chapter = str(self._chapter("x.html", "<h1>X</h1>"))
        code = make_epub.main(["--title", "T", "--author", "A", "--output", str(self.dir / "notes.txt"), chapter])
        self.assertEqual(code, 2)
        self.assertFalse((self.dir / "notes.txt").exists())

    def test_existing_non_epub_file_is_never_overwritten(self) -> None:
        victim = self.dir / "important.epub"
        victim.write_text("not a book")
        chapter = str(self._chapter("x.html", "<h1>X</h1>"))
        code = make_epub.main(["--title", "T", "--author", "A", "--output", str(victim), chapter])
        self.assertEqual(code, 2)
        self.assertEqual(victim.read_text(), "not a book")

    def test_existing_epub_can_be_rebuilt(self) -> None:
        chapter = str(self._chapter("x.html", "<h1>X</h1>"))
        output = str(self.dir / "again.epub")
        self.assertEqual(make_epub.main(["--title", "T", "--author", "A", "--output", output, chapter]), 0)
        self.assertEqual(make_epub.main(["--title", "T", "--author", "A", "--output", output, chapter]), 0)

    def _body(self, html: str) -> str:
        chapter = self._build([self._chapter("b.html", "<h1>T</h1>" + html)]).read("OEBPS/chapter-001.xhtml")
        return chapter.decode()

    def test_implicitly_closed_list_items_and_paragraphs(self) -> None:
        body = self._body("<ul><li>a<li>b</ul><p>one<p>two<p>three<div>block</div>")
        self.assertIn("<ul><li>a</li><li>b</li></ul>", body)
        self.assertIn("<p>one</p><p>two</p><p>three</p><div>block</div>", body)

    def test_nested_links_are_not_produced(self) -> None:
        body = self._body('<p><a href="https://a.example">one<a href="https://b.example">two</a></p>')
        self.assertIn('<a href="https://a.example">one</a><a href="https://b.example">two</a>', body)

    def test_empty_h1_does_not_duplicate_the_title(self) -> None:
        chapter = self._build([self._chapter("notes.html", "<h1> </h1><p>x</p>")]).read("OEBPS/chapter-001.xhtml")
        self.assertEqual(chapter.decode().count("<h1>"), 1)

    def test_xmp_content_is_literal_text(self) -> None:
        body = self._body("<xmp><b>not bold</b></xmp>")
        self.assertIn("<pre>&lt;b&gt;not bold&lt;/b&gt;</pre>", body)

    def test_invalid_language_exits_2(self) -> None:
        chapter = str(self._chapter("x.html", "<h1>X</h1>"))
        code = make_epub.main(["--title", "T", "--author", "A", "--output", str(self.dir / "o.epub"),
                               "--language", 'en" x="', chapter])
        self.assertEqual(code, 2)

    def test_blank_title_or_author_exits_2(self) -> None:
        chapter = str(self._chapter("x.html", "<h1>X</h1>"))
        for title, author in (("  ", "A"), ("T", "")):
            code = make_epub.main(["--title", title, "--author", author,
                                   "--output", str(self.dir / "o.epub"), chapter])
            self.assertEqual(code, 2)

    def test_cover_is_optional(self) -> None:
        without = self._build(self._two_chapters())
        self.assertNotIn("OEBPS/cover.xhtml", without.namelist())
        book = self._build(self._two_chapters(), cover=True)
        cover = book.read("OEBPS/cover.xhtml").decode()
        for text in ("Project Plan", "Test Reader", "2026-10-05"):
            self.assertIn(text, cover)
        opf = ET.fromstring(book.read("OEBPS/content.opf"))
        spine = [ref.get("idref") for ref in opf.iterfind(".//opf:spine/opf:itemref", NS)]
        self.assertEqual(spine[0], "cover")

    def test_every_xml_file_is_well_formed(self) -> None:
        book = self._build(self._two_chapters(), cover=True)
        for name in book.namelist():
            if name.endswith((".xhtml", ".opf", ".ncx", ".xml")):
                ET.fromstring(book.read(name))

    def test_non_ascii_metadata_and_content(self) -> None:
        output = self.dir / "año.epub"
        chapters = [self._chapter("c.html", "<h1>Capítulo uno</h1><p>Señora & niño</p>")]
        make_epub.build_epub(output, "Cien años", "José Ñúñez", chapters, date="2026-10-05")
        book = zipfile.ZipFile(output)
        opf = ET.fromstring(book.read("OEBPS/content.opf"))
        self.assertEqual(opf.findtext(".//dc:title", namespaces=NS), "Cien años")
        self.assertEqual(opf.findtext(".//dc:creator", namespaces=NS), "José Ñúñez")
        chapter = ET.fromstring(book.read("OEBPS/chapter-001.xhtml"))
        self.assertIn("Señora & niño", "".join(chapter.itertext()))

    def test_main_reports_the_output(self) -> None:
        output = self.dir / "cli.epub"
        code = make_epub.main(["--title", "T", "--author", "A", "--output", str(output),
                               str(self._chapter("x.html", "<h1>X</h1>"))])
        self.assertEqual(code, 0)
        self.assertTrue(zipfile.is_zipfile(output))

    def test_missing_chapter_file_exits_2(self) -> None:
        code = make_epub.main(["--title", "T", "--author", "A", "--output", str(self.dir / "o.epub"),
                               str(self.dir / "missing.html")])
        self.assertEqual(code, 2)

    def test_invalid_date_exits_2(self) -> None:
        code = make_epub.main(["--title", "T", "--author", "A", "--output", str(self.dir / "o.epub"),
                               "--date", "05/10/2026", str(self._chapter("x.html", "<p>x</p>"))])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
