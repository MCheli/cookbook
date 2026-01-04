#!/usr/bin/env python3
"""
Build PDF versions of recipes.

Usage:
    python scripts/build-pdf.py              # Build all category PDFs
    python scripts/build-pdf.py --all        # Build single combined PDF
    python scripts/build-pdf.py --individual # Build individual recipe PDFs
"""

import os
import sys
import argparse
import markdown
from pathlib import Path

try:
    from weasyprint import HTML
except ImportError:
    print("Error: weasyprint is required. Install with: pip install weasyprint")
    sys.exit(1)

RECIPE_DIRS = [
    ('instapot', 'Instant Pot Recipes'),
    ('crockpot', 'Crockpot Recipes'),
    ('stovetop-oven', 'Stovetop & Oven Recipes'),
]

CSS_STYLES = """
@page {
    size: letter;
    margin: 0.5in;
    @bottom-center {
        content: counter(page);
        font-size: 9pt;
        color: #666;
    }
}
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
    font-size: 10pt;
    line-height: 1.3;
    color: #333;
}
h1 {
    color: #2d5a27;
    border-bottom: 2px solid #2d5a27;
    padding-bottom: 0.3em;
    margin-bottom: 0.5em;
    font-size: 18pt;
}
h2 {
    color: #2d5a27;
    margin-top: 0;
    margin-bottom: 0.3em;
    font-size: 14pt;
    page-break-after: avoid;
}
h3 {
    color: #555;
    margin-top: 0.6em;
    margin-bottom: 0.3em;
    font-size: 11pt;
    page-break-after: avoid;
}
p {
    margin: 0.3em 0;
}
table {
    width: 100%;
    border-collapse: collapse;
    margin: 0.4em 0;
    font-size: 9pt;
}
th, td {
    border: 1px solid #ddd;
    padding: 3px 6px;
    text-align: left;
}
th {
    background-color: #f5f5f5;
    font-weight: 600;
}
tr:nth-child(even) {
    background-color: #fafafa;
}
ol, ul {
    margin: 0.4em 0;
    padding-left: 1.2em;
}
li {
    margin-bottom: 0.2em;
}
.page-break {
    page-break-before: always;
}
"""


def md_to_html(md_content, title=None):
    """Convert markdown to styled HTML."""
    html_body = markdown.markdown(md_content, extensions=['extra', 'tables'])

    title_html = f"<h1>{title}</h1>" if title else ""

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>{CSS_STYLES}</style>
    </head>
    <body>
        {title_html}
        {html_body}
    </body>
    </html>
    """


def combine_recipes(folder_path, title):
    """Combine all recipe markdown files in a folder."""
    recipes = []

    for filename in sorted(os.listdir(folder_path)):
        if filename.endswith('.md'):
            filepath = os.path.join(folder_path, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            recipes.append(content)

    # Join with page breaks
    combined = '\n\n<div class="page-break"></div>\n\n'.join(recipes)
    return md_to_html(combined, title)


def build_category_pdfs(base_dir, output_dir):
    """Build one PDF per recipe category."""
    os.makedirs(output_dir, exist_ok=True)
    recipes_dir = os.path.join(base_dir, 'recipes')

    for folder, title in RECIPE_DIRS:
        folder_path = os.path.join(recipes_dir, folder)
        if not os.path.exists(folder_path):
            print(f"  Skipping {folder} (not found)")
            continue

        output_path = os.path.join(output_dir, f'{folder}.pdf')
        html_content = combine_recipes(folder_path, title)
        HTML(string=html_content).write_pdf(output_path)
        print(f"  Created: pdf/{folder}.pdf")

    print(f"\nGenerated {len(RECIPE_DIRS)} category PDFs")


def build_combined_pdf(base_dir, output_dir):
    """Build a single PDF with all recipes."""
    os.makedirs(output_dir, exist_ok=True)
    recipes_dir = os.path.join(base_dir, 'recipes')

    all_content = []

    for folder, title in RECIPE_DIRS:
        folder_path = os.path.join(recipes_dir, folder)
        if not os.path.exists(folder_path):
            continue

        # Add category header
        all_content.append(f"# {title}\n")

        for filename in sorted(os.listdir(folder_path)):
            if filename.endswith('.md'):
                filepath = os.path.join(folder_path, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                all_content.append(content)

    combined = '\n\n<div class="page-break"></div>\n\n'.join(all_content)
    html_content = md_to_html(combined, "Cookbook")

    output_path = os.path.join(output_dir, 'cookbook.pdf')
    HTML(string=html_content).write_pdf(output_path)
    print(f"  Created: pdf/cookbook.pdf")


def build_individual_pdfs(base_dir, output_dir):
    """Build individual PDFs for each recipe."""
    recipes_dir = os.path.join(base_dir, 'recipes')
    count = 0

    for folder, _ in RECIPE_DIRS:
        folder_path = os.path.join(recipes_dir, folder)
        if not os.path.exists(folder_path):
            continue

        pdf_folder = os.path.join(output_dir, folder)
        os.makedirs(pdf_folder, exist_ok=True)

        for filename in sorted(os.listdir(folder_path)):
            if filename.endswith('.md'):
                filepath = os.path.join(folder_path, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                html_content = md_to_html(content)
                pdf_name = filename.replace('.md', '.pdf')
                output_path = os.path.join(pdf_folder, pdf_name)
                HTML(string=html_content).write_pdf(output_path)
                count += 1

    print(f"  Generated {count} individual recipe PDFs")


def main():
    parser = argparse.ArgumentParser(description='Build PDF versions of recipes')
    parser.add_argument('--all', action='store_true', help='Build single combined PDF (default)')
    parser.add_argument('--categories', action='store_true', help='Build separate PDFs per category')
    parser.add_argument('--individual', action='store_true', help='Build individual recipe PDFs')
    args = parser.parse_args()

    base_dir = Path(__file__).parent.parent
    output_dir = os.path.join(base_dir, 'pdf')

    if args.categories:
        print("Building category PDFs...")
        build_category_pdfs(base_dir, output_dir)
    elif args.individual:
        print("Building individual recipe PDFs...")
        build_individual_pdfs(base_dir, output_dir)
    else:
        # Default: build combined cookbook.pdf
        print("Building combined cookbook PDF...")
        build_combined_pdf(base_dir, output_dir)


if __name__ == '__main__':
    main()
