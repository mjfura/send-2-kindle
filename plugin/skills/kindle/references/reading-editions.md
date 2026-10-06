# Reading editions

A reading edition presents the same content so it reads well on a Kindle. Never drop or invent
content; only restructure and format it. Write each chapter as an HTML fragment (body content only)
and let `make_epub.py` package them.

## Chapters

- One chapter per top-level section of the source (`#` or `##` in Markdown); start each with `<h1>`.
- Put a short front chapter first for editions of existing files: title, source file name, date.
- Use `<h2>`/`<h3>` for subsections, `<p>` for paragraphs.

## Converting Markdown faithfully

| Markdown | HTML |
|---|---|
| `**bold**`, `*italic*`, `` `code` `` | `<strong>`, `<em>`, `<code>` |
| lists, numbered lists | `<ul>`/`<ol>` with `<li>` |
| `- [ ] task` / `- [x] task` | `<li>☐ task</li>` / `<li>☑ task</li>` |
| `[text](url)` | `<a href="url">text</a>` (keep the URL visible if the link matters) |
| tables | `<table>` with `<th>` headers; turn tables wider than ~4 columns into one list per row for 6–7" screens |
| fenced code | `<pre><code>…</code></pre>`, escaping `<`, `>` and `&` |
| `> quote` | `<blockquote>` |
| images | describe them in text; images are not embedded |

## By document type

- **Plan:** an "Overview" chapter (goal, architecture, task list with ☐), then one chapter per task.
- **Spec / design:** decisions table near the start, then sections in order.
- **Report or summary you write:** executive summary first, then details, then decisions and next steps.
- **Proposals:** one chapter per proposal with its pros, cons and recommendation.

## Before building

Check every chapter starts with `<h1>`, nothing from the source is missing, and code and tables
survived. `make_epub.py` repairs malformed HTML, but well-structured input reads better.
