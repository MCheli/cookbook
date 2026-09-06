# Cookbook

A personal cookbook with recipes organized by cooking method. Includes a website for browsing and selecting recipes, with automatic grocery list generation and Amazon Whole Foods integration.

## Features

- **36 recipes** organized by cooking method (Instant Pot, Crockpot, Stovetop & Oven, Campfire)
- **Website** for browsing recipes and generating grocery lists
- **Amazon Whole Foods links** for easy shopping
- **PDF generation** for printable versions
- **Easy to extend** - just add a markdown file

## Quick Start

```bash
# Build website and start local server
make serve

# Open http://localhost:8080 in your browser
```

## Project Structure

```
cookbook/
├── recipes/                    # Recipe markdown files
│   ├── instapot/              # Instant Pot recipes
│   ├── crockpot/              # Crockpot recipes
│   ├── stovetop-oven/         # Stovetop & oven recipes
│   └── campfire/              # Campfire & foil packet recipes
├── website/                    # Generated website files
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   └── recipes.js             # Auto-generated from markdown
├── pdf/                        # Generated PDF files
├── scripts/                    # Build scripts
│   ├── build-website.js       # Generates recipes.js
│   ├── build-pdf.py           # Generates PDFs
│   └── split-recipes.js       # Utility to split recipe files
└── Makefile                    # Build automation
```

## Build Commands

| Command | Description |
|---------|-------------|
| `make` | Build website and cookbook.pdf |
| `make website` | Build website/recipes.js from recipe files |
| `make pdf` | Build combined cookbook.pdf with all recipes |
| `make pdf-categories` | Build separate PDFs per category |
| `make pdf-individual` | Build individual recipe PDFs |
| `make serve` | Build website and start local server |
| `make clean` | Remove generated files |
| `make help` | Show all available commands |

## Adding a New Recipe

1. Create a new `.md` file in the appropriate folder:
   - `recipes/instapot/` - Instant Pot recipes
   - `recipes/crockpot/` - Crockpot recipes
   - `recipes/stovetop-oven/` - Stovetop & oven recipes
   - `recipes/campfire/` - Campfire & foil packet recipes

2. Use this template:

```markdown
## Recipe Title

**Servings:** 4 | **Prep:** 10 min | **Cook:** 20 min

### Ingredients
| Group | Item | Amount |
|-------|------|--------|
| **Protein** | Chicken breast | 1 lb |
| **Vegetables** | Onion, diced | 1 medium |
| | Garlic, minced | 2 cloves |
| **Seasoning** | Salt & pepper | to taste |

### Method
1. First step of the recipe.
2. Second step of the recipe.
3. Continue with remaining steps.

### Grocery List
- **Protein**: 1 lb chicken breast
- **Vegetables**: 1 onion, garlic
- **Seasoning**: Salt, pepper
```

3. Rebuild:
```bash
make website  # Update the website
make pdf      # Update PDFs
```

## Recipe Format Details

### Ingredients Table

The ingredients table uses three columns:
- **Group**: Category like "Protein", "Vegetables", "Seasoning" (bold with `**`)
- **Item**: The ingredient name
- **Amount**: Quantity needed

Leave the Group cell empty to continue the previous group:
```markdown
| **Vegetables** | Onion | 1 medium |
| | Garlic | 2 cloves |
| | Bell pepper | 1 |
```

### Method Steps

Numbered steps with optional bold keywords:
```markdown
1. **Prep** - Dice the vegetables and set aside.
2. **Cook** - Heat oil in a pan over medium heat.
```

## Requirements

- **Node.js** - For building the website
- **Python 3** - For generating PDFs
- **WeasyPrint** - PDF generation library

Install WeasyPrint:
```bash
pip install weasyprint markdown
```

## Using the Website

1. **Browse recipes** - View all recipes or filter by category
2. **Select recipes** - Click recipe cards to add them to your meal plan
3. **Generate grocery list** - Click "Generate Grocery List" to see combined ingredients
4. **Shop on Amazon** - Click "Whole Foods" buttons to search for items on Amazon Fresh

## License

MIT
