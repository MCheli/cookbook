"""Printable PDFs, rendered exactly as the old `scripts/build-pdf.py` rendered the markdown files:
the recipe's markdown through Python-Markdown, with the same stylesheet, one recipe per page."""

from __future__ import annotations

import markdown as md

CSS_STYLES = """
@page {
    size: letter;
    margin: 0.5in;
    @bottom-center { content: counter(page); font-size: 9pt; color: #666; }
}
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, 'Noto Color Emoji', sans-serif;
    font-size: 10pt; line-height: 1.3; color: #333;
}
h1 { color: #2d5a27; border-bottom: 2px solid #2d5a27; padding-bottom: 0.3em; margin-bottom: 0.5em; font-size: 18pt; }
h2 { color: #2d5a27; margin-top: 0; margin-bottom: 0.3em; font-size: 14pt; page-break-after: avoid; }
h3 { color: #555; margin-top: 0.6em; margin-bottom: 0.3em; font-size: 11pt; page-break-after: avoid; }
p { margin: 0.3em 0; }
table { width: 100%; border-collapse: collapse; margin: 0.4em 0; font-size: 9pt; }
th, td { border: 1px solid #ddd; padding: 3px 6px; text-align: left; }
th { background-color: #f5f5f5; font-weight: 600; }
tr:nth-child(even) { background-color: #fafafa; }
ol, ul { margin: 0.4em 0; padding-left: 1.2em; }
li { margin-bottom: 0.2em; }
.page-break { page-break-before: always; }
"""


def markdown_to_html(markdowns: list[str], title: str | None = None) -> str:
    combined = '\n\n<div class="page-break"></div>\n\n'.join(markdowns)
    body = md.markdown(combined, extensions=["extra", "tables"])
    title_html = f"<h1>{title}</h1>" if title else ""
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        f"<style>{CSS_STYLES}</style></head><body>{title_html}{body}</body></html>"
    )


def render_pdf(markdowns: list[str], title: str | None = None) -> bytes:
    from weasyprint import HTML  # heavy import; only when a PDF is asked for

    return HTML(string=markdown_to_html(markdowns, title)).write_pdf()
