"""Printed recipes: one page each, however long the recipe."""

import io
import json
from pathlib import Path

from pypdf import PdfReader

from app.services.pdf import render_pdf, split_ingredients

SEEDS = json.loads((Path(__file__).parents[1] / "app/seed/recipes.json").read_text())


def _pages(pdf: bytes) -> list[str]:
    return [p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages]


def _long_recipe(ingredients: int, steps: int) -> str:
    rows = "".join(
        f"| Produce | Ingredient {i}, chopped | {i} cups |\n" for i in range(ingredients)
    )
    step = "Stir everything together and keep cooking until it looks right, scraping the bottom. "
    method = "".join(f"{i}. **Step {i}:** {step * 2}\n" for i in range(1, steps + 1))
    return (
        "## 🍲 Long Stew\n**Servings:** 8 | **Prep:** 30 min | **Cook:** 4 hr\n\n"
        "### Ingredients\n| Category | Item | Amount |\n|---|---|---|\n"
        f"{rows}\n### Method\n{method}"
    )


def test_every_bundled_recipe_prints_on_one_page_numbered_across_the_pdf():
    pages = _pages(render_pdf([r["markdown"] for r in SEEDS]))
    assert len(pages) == len(SEEDS)
    assert pages[0].strip().endswith("1") and pages[-1].strip().endswith(str(len(SEEDS)))


def test_a_long_recipe_is_fitted_onto_one_page():
    pages = _pages(render_pdf([_long_recipe(30, 15), SEEDS[0]["markdown"]]))
    assert len(pages) == 2
    assert "Ingredient 29" in pages[0] and "Step 15" in pages[0]


def test_compact_layout_pairs_ingredient_columns_without_categories():
    html = "<p>x</p><table><thead><tr><th>Category</th><th>Item</th><th>Amount</th></tr></thead><tbody>"
    html += "".join(
        f"<tr><td>Produce</td><td>Item {i}</td><td>{i} cups</td></tr>" for i in range(9)
    )
    html += "</tbody></table><ol><li>step</li></ol>"
    out = split_ingredients(html)
    assert out.count("<table") == 1 and "Produce" not in out
    assert '<td>Item 0</td><td>0 cups</td><td class="pair">Item 5</td>' in out
    assert out.endswith("<ol><li>step</li></ol>")
    short = "<table><thead><tr><th>Category</th><th>Item</th><th>Amount</th></tr></thead><tbody><tr><td>a</td><td>b</td><td>c</td></tr></tbody></table>"
    assert split_ingredients(short) == short
