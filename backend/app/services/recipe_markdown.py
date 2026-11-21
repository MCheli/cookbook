"""The cookbook's original markdown format, both ways.

Every recipe that lived in `recipes/<method>/*.md` is imported with `parse_markdown`, and
`to_markdown` writes a recipe back out in the same shape. `tests/test_recipe_markdown.py` proves
the round trip for all bundled recipes, and the PDF and print views are rendered from this
markdown, so a recipe looks exactly as it did before the database.

    ## 🍝 Title
    **Servings:** 4 | **Prep:** 10 min | **Cook:** 20 min (stovetop)

    ### Ingredients
    | Group | Item | Amount |
    |-------|------|--------|
    | **Pasta** | Penne or rigatoni | 1 lb |
    | | Garlic, minced | 3 cloves |

    ### Method
    1. **Cook Pasta** – Boil pasta ...

    ### Grocery List
    - **Pasta**: 1 lb penne or rigatoni
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

_META_LABELS = ("**Servings:**", "**Prep:**", "**Cook:**")


def _parse_meta(line: str) -> tuple[str, str, str] | None:
    """'**Servings:** 4 | **Prep:** 10 min | **Cook:** 20 min' → its three values.

    Split on '|' rather than one regex: the regex's runs of optional whitespace backtracked
    cubically on long lines (CodeQL py/polynomial-redos), and this is linear."""
    parts = line.split("|", 2)
    if len(parts) != 3:
        return None
    values = []
    for label, part in zip(_META_LABELS, parts, strict=True):
        part = part.strip()
        if not part.startswith(label):
            return None
        values.append(part[len(label) :].strip())
    return values[0], values[1], values[2]


_STEP_RE = re.compile(r"^\d+\.\s+(.*)$")


@dataclass
class IngredientRow:
    group: str | None
    item: str
    amount: str | None


@dataclass
class RecipeDoc:
    title: str
    emoji: str | None = None
    servings_text: str | None = None
    prep_text: str | None = None
    cook_text: str | None = None
    ingredients: list[IngredientRow] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    grocery: list[str] = field(default_factory=list)


def _is_emoji_char(ch: str) -> bool:
    if ch in "‍️︎":
        return True
    cp = ord(ch)
    if 0x1F000 <= cp <= 0x1FAFF or 0x2600 <= cp <= 0x27BF or 0x2B00 <= cp <= 0x2BFF:
        return True
    return unicodedata.category(ch) == "So"


def split_emoji(heading: str) -> tuple[str | None, str]:
    """'🍝 Pasta' -> ('🍝', 'Pasta'). Headings without a leading emoji keep it None."""
    heading = heading.strip()
    i = 0
    while i < len(heading) and _is_emoji_char(heading[i]):
        i += 1
    if i == 0:
        return None, heading
    return heading[:i], heading[i:].strip()


def _sections(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"_head": []}
    current = "_head"
    for line in text.splitlines():
        if line.startswith("### "):
            current = line[4:].strip().lower()
            out[current] = []
        else:
            out[current].append(line)
    return out


def _cells(row: str) -> list[str]:
    inner = row.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [c.strip() for c in inner.split("|")]


def _unbold(s: str) -> str:
    s = s.strip()
    if s.startswith("**") and s.endswith("**") and len(s) >= 4:
        return s[2:-2].strip()
    return s


def parse_markdown(text: str) -> RecipeDoc:
    sections = _sections(text)
    title_line = next((ln for ln in sections["_head"] if ln.startswith("## ")), None)
    if title_line is None:
        raise ValueError("recipe markdown needs a '## Title' heading")
    emoji, title = split_emoji(title_line[3:])
    doc = RecipeDoc(title=title, emoji=emoji)

    for ln in sections["_head"]:
        meta = _parse_meta(ln.strip())
        if meta:
            doc.servings_text, doc.prep_text, doc.cook_text = (v or None for v in meta)

    group: str | None = None
    rows = [ln for ln in sections.get("ingredients", []) if ln.strip().startswith("|")]
    for row in rows[2:]:  # header + separator
        cells = _cells(row)
        if len(cells) < 3:
            continue
        raw_group, item, amount = cells[0], cells[1], cells[2]
        if raw_group:
            group = _unbold(raw_group)
        if item:
            doc.ingredients.append(IngredientRow(group=group, item=item, amount=amount or None))

    for ln in sections.get("method", []):
        m = _STEP_RE.match(ln.strip())
        if m:
            doc.steps.append(m.group(1).strip())
        elif ln.strip() and doc.steps:  # a wrapped continuation line
            doc.steps[-1] += " " + ln.strip()

    for ln in sections.get("grocery list", []):
        s = ln.strip()
        if s.startswith("- "):
            doc.grocery.append(s[2:].strip())

    return doc


def to_markdown(doc: RecipeDoc) -> str:
    title = f"{doc.emoji} {doc.title}" if doc.emoji else doc.title
    lines = [f"## {title}", ""]
    if doc.servings_text or doc.prep_text or doc.cook_text:
        lines += [
            f"**Servings:** {doc.servings_text or ''} | **Prep:** {doc.prep_text or ''} | "
            f"**Cook:** {doc.cook_text or ''}",
            "",
        ]
    lines += ["### Ingredients", "| Group | Item | Amount |", "|-------|------|--------|"]
    previous: str | None = None
    for ing in doc.ingredients:
        group_cell = f"**{ing.group}**" if ing.group and ing.group != previous else ""
        previous = ing.group if ing.group else previous
        lines.append(f"| {group_cell} | {ing.item} | {ing.amount or ''} |")
    lines += ["", "### Method"]
    lines += [f"{i}. {step}" for i, step in enumerate(doc.steps, 1)]
    if doc.grocery:
        lines += ["", "### Grocery List"]
        lines += [f"- {g}" for g in doc.grocery]
    return "\n".join(lines) + "\n"


def normalize(text: str) -> str:
    """Whitespace-insensitive form used to compare markdown (tests and import checks)."""
    out = []
    for ln in text.splitlines():
        # Some files separate the Servings/Prep/Cook line with em spaces; that's layout, not content.
        ln = ln.replace("\u2003", " ").replace("\u202f", " ").rstrip()
        if re.fullmatch(r"\|[\s\-:|]+\|", ln):
            ln = "|---|---|---|"
        elif ln.startswith("|"):
            ln = "| " + " | ".join(_cells(ln)) + " |"
        out.append(ln)
    joined = "\n".join(out).strip()
    return re.sub(r"\n{3,}", "\n\n", joined)
