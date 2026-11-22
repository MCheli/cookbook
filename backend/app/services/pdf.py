"""Printable PDFs, rendered exactly as the old `scripts/build-pdf.py` rendered the markdown files:
the recipe's markdown through Python-Markdown, with the same stylesheet, one recipe per page."""

from __future__ import annotations

import re

import markdown as md

# The old stylesheet, with sizes relative to the body so one number can shrink a long recipe:
# at scale 1 this is exactly the old 10pt body, 18/14/11pt headings and 9pt tables.
CSS_TEMPLATE = """
@page {
    size: letter;
    margin: %(margin)sin;
    @bottom-center { content: "%(page)s"; font-size: 9pt; color: #666; }
}
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, 'Noto Color Emoji', sans-serif;
    font-size: %(body)spt; line-height: 1.3; color: #333;
}
h1 { color: #2d5a27; border-bottom: 2px solid #2d5a27; padding-bottom: 0.3em; margin-bottom: 0.5em; font-size: 1.8em; }
h2 { color: #2d5a27; margin-top: 0; margin-bottom: 0.3em; font-size: 1.4em; page-break-after: avoid; }
h3 { color: #555; margin-top: 0.6em; margin-bottom: 0.3em; font-size: 1.1em; page-break-after: avoid; }
p { margin: 0.3em 0; }
table { width: 100%%; border-collapse: collapse; margin: 0.4em 0; font-size: 0.9em; }
th, td { border: 1px solid #ddd; padding: 0.33em 0.67em; text-align: left; }
th { background-color: #f5f5f5; font-weight: 600; }
tr:nth-child(even) { background-color: #fafafa; }
ol, ul { margin: 0.4em 0; padding-left: 1.2em; }
li { margin-bottom: 0.2em; }
.ing-split td.pair, .ing-split th.pair { border-left: 2px solid #bbb; }
"""

# Layouts to try, in order, until a recipe fits on one page: the normal one at slightly smaller
# sizes first, then a compact one (ingredients in two columns without the category column,
# narrower margins), so a long recipe gets a denser layout before it gets small print. Below
# 7pt it prints on two pages rather than becoming unreadable.
ATTEMPTS = [(False, s) for s in (10, 9.5, 9)] + [(True, s) for s in (10, 9.5, 9, 8.5, 8, 7.5, 7)]

_TABLE = re.compile(r"<table>.*?</table>", re.S)
_ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)


def split_ingredients(html: str) -> str:
    """The first table (the ingredients) folded into two Item | Amount column pairs, without the
    category column: half the rows, side by side, in one table (one table renders reliably)."""
    m = _TABLE.search(html)
    if not m:
        return html
    rows = [_CELL.findall(r) for r in _ROW.findall(m.group(0))]
    head, body = rows[0], [r for r in rows[1:] if len(r) >= 3]
    if len(head) < 3 or len(body) < 8:  # short or unusual tables stay as they are
        return html
    half = (len(body) + 1) // 2
    left, right = body[:half], body[half:]
    lines = []
    for n, row in enumerate(left):
        other = right[n] if n < len(right) else ["", "", ""]
        lines.append(
            f"<tr><td>{row[1]}</td><td>{row[2]}</td>"
            f'<td class="pair">{other[1]}</td><td>{other[2]}</td></tr>'
        )
    head_cells = f"<th>{head[1]}</th><th>{head[2]}</th>"
    table = (
        f'<table class="ing-split"><thead><tr>{head_cells}'
        f'<th class="pair">{head[1]}</th><th>{head[2]}</th></tr></thead>'
        f"<tbody>{''.join(lines)}</tbody></table>"
    )
    return html[: m.start()] + table + html[m.end() :]


def recipe_html(
    markdown_text: str,
    *,
    page: int | str = "",
    body_pt: float = 10,
    compact: bool = False,
    title: str | None = None,
) -> str:
    body = md.markdown(markdown_text, extensions=["extra", "tables"])
    if compact:
        body = split_ingredients(body)
    title_html = f"<h1>{title}</h1>" if title else ""
    css = CSS_TEMPLATE % {"page": page, "body": body_pt, "margin": 0.4 if compact else 0.5}
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        f"<style>{css}</style></head><body>{title_html}{body}</body></html>"
    )


def render_pdf(markdowns: list[str], title: str | None = None) -> bytes:
    """One recipe per page: each is laid out on its own and, if it runs past a page, re-laid out
    smaller or more compactly (ATTEMPTS) until it fits. Pages are numbered across the PDF."""
    from weasyprint import HTML  # heavy import; only when a PDF is asked for

    pages = []
    first = None
    for n, text in enumerate(markdowns, start=1):
        for compact, size in ATTEMPTS:
            html = recipe_html(
                text, page=n, body_pt=size, compact=compact, title=title if n == 1 else None
            )
            doc = HTML(string=html).render()
            if len(doc.pages) == 1:
                break
        first = first or doc
        pages.extend(doc.pages)
    if first is None:
        raise ValueError("No recipes to print")
    return first.copy(pages).write_pdf()
