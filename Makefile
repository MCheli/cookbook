# Cookbook Makefile
# Build website and PDF versions of recipes

.PHONY: all website pdf pdf-categories pdf-individual clean serve help

# Default target: build website and cookbook PDF
all: website pdf

# Build the website (generates website/recipes.js from recipe markdown files)
website:
	@echo "Building website..."
	@node scripts/build-website.js

# Build combined cookbook.pdf
pdf:
	@echo "Building cookbook.pdf..."
	@python3 scripts/build-pdf.py --all

# Build separate PDFs per category
pdf-categories:
	@echo "Building category PDFs..."
	@python3 scripts/build-pdf.py --categories

# Build individual PDFs for each recipe
pdf-individual:
	@echo "Building individual recipe PDFs..."
	@python3 scripts/build-pdf.py --individual

# Start a local development server
serve: website
	@echo "Starting server at http://localhost:8080"
	@cd website && python3 -m http.server 8080

# Clean generated files
clean:
	@echo "Cleaning generated files..."
	@rm -f website/recipes.js
	@rm -f pdf/*.pdf
	@rm -rf pdf/instapot pdf/crockpot pdf/stovetop-oven pdf/campfire
	@echo "Done"

# Show help
help:
	@echo "Cookbook Build System"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  all            Build website and cookbook.pdf (default)"
	@echo "  website        Build website/recipes.js from recipe markdown files"
	@echo "  pdf            Build combined cookbook.pdf with all recipes"
	@echo "  pdf-categories Build separate PDFs per category"
	@echo "  pdf-individual Build individual PDFs for each recipe"
	@echo "  serve          Build website and start local development server"
	@echo "  clean          Remove all generated files"
	@echo "  help           Show this help message"
	@echo ""
	@echo "Recipe files are located in:"
	@echo "  recipes/instapot/      - Instant Pot recipes"
	@echo "  recipes/crockpot/      - Crockpot recipes"
	@echo "  recipes/stovetop-oven/ - Stovetop & oven recipes"
	@echo "  recipes/campfire/      - Campfire & foil packet recipes"
