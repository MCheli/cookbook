#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const RECIPE_DIRS = [
  { folder: 'instapot', category: 'Instant Pot' },
  { folder: 'crockpot', category: 'Crockpot' },
  { folder: 'stovetop-oven', category: 'Stovetop & Oven' },
  { folder: 'campfire', category: 'Campfire' }
];

function parseIngredients(tableContent) {
  const ingredients = [];
  const lines = tableContent.split('\n').filter(line => line.trim().startsWith('|'));

  let currentGroup = '';

  // Skip header and separator rows
  for (let i = 2; i < lines.length; i++) {
    const line = lines[i];
    const cells = line.split('|').map(c => c.trim());
    cells.shift();
    cells.pop();

    if (cells.length >= 3) {
      const rawGroup = cells[0] || '';
      const item = cells[1] || '';
      const amount = cells[2] || '';

      if (rawGroup) {
        currentGroup = rawGroup.replace(/\*\*/g, '').trim();
      }

      if (item && item !== 'Item') {
        ingredients.push({
          group: currentGroup,
          item: item,
          amount: amount
        });
      }
    }
  }

  return ingredients;
}

function parseRecipeFile(content, category) {
  // Extract title from ## header
  const titleMatch = content.match(/^## (.+)$/m);
  if (!titleMatch) return null;

  const titleLine = titleMatch[1].trim();
  // Remove all emojis from title (comprehensive Unicode emoji ranges)
  const title = titleLine
    .replace(/[\u{1F300}-\u{1F9FF}]/gu, '')  // Misc symbols, emoticons, etc.
    .replace(/[\u{1FA00}-\u{1FAFF}]/gu, '')  // Symbols and pictographs extended-A
    .replace(/[\u{2600}-\u{26FF}]/gu, '')    // Misc symbols
    .replace(/[\u{2700}-\u{27BF}]/gu, '')    // Dingbats
    .replace(/[\u{FE00}-\u{FE0F}]/gu, '')    // Variation selectors
    .replace(/[\u{1F000}-\u{1F02F}]/gu, '')  // Mahjong, dominos
    .replace(/[\u{1F0A0}-\u{1F0FF}]/gu, '')  // Playing cards
    .replace(/^\s+/, '')                      // Leading whitespace
    .trim();

  // Extract servings and time info
  const infoMatch = content.match(/\*\*Servings:\*\*\s*([^|]+)\s*\|\s*\*\*Prep:\*\*\s*([^|]+)\s*\|\s*\*\*Cook:\*\*\s*(.+)/);
  const servings = infoMatch ? infoMatch[1].trim() : '';
  const prepTime = infoMatch ? infoMatch[2].trim() : '';
  const cookTime = infoMatch ? infoMatch[3].trim().split('\n')[0] : '';

  // Extract ingredients table
  const ingredientsMatch = content.match(/### Ingredients\s*([\s\S]*?)(?=###|$)/);
  const ingredients = ingredientsMatch ? parseIngredients(ingredientsMatch[1]) : [];

  // Extract method
  const methodMatch = content.match(/### Method\s*([\s\S]*?)(?=###|$)/);
  const methodContent = methodMatch ? methodMatch[1].trim() : '';
  const methodSteps = methodContent
    .split(/^\d+\.\s*/gm)
    .filter(s => s.trim())
    .map(s => s.replace(/\n/g, ' ').trim());

  if (title && ingredients.length > 0) {
    return {
      id: title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, ''),
      title: title,
      category: category,
      servings: servings,
      prepTime: prepTime,
      cookTime: cookTime,
      ingredients: ingredients,
      method: methodSteps
    };
  }

  return null;
}

function main() {
  const allRecipes = [];
  const baseDir = path.join(__dirname, '..');
  const recipesDir = path.join(baseDir, 'recipes');

  for (const { folder, category } of RECIPE_DIRS) {
    const folderPath = path.join(recipesDir, folder);

    if (!fs.existsSync(folderPath)) {
      console.log(`Skipping ${folder} (not found)`);
      continue;
    }

    const files = fs.readdirSync(folderPath).filter(f => f.endsWith('.md')).sort();
    let count = 0;

    for (const file of files) {
      const filePath = path.join(folderPath, file);
      const content = fs.readFileSync(filePath, 'utf-8');
      const recipe = parseRecipeFile(content, category);

      if (recipe) {
        allRecipes.push(recipe);
        count++;
      }
    }

    console.log(`Parsed ${count} recipes from recipes/${folder}/`);
  }

  // Ensure website directory exists
  const websiteDir = path.join(baseDir, 'website');
  if (!fs.existsSync(websiteDir)) {
    fs.mkdirSync(websiteDir, { recursive: true });
  }

  // Generate JavaScript file
  const output = `// Auto-generated from recipe markdown files
// Run 'make website' or 'node scripts/build-website.js' to regenerate

const RECIPES = ${JSON.stringify(allRecipes, null, 2)};
`;

  const outputPath = path.join(websiteDir, 'recipes.js');
  fs.writeFileSync(outputPath, output);
  console.log(`\nGenerated website/recipes.js with ${allRecipes.length} total recipes`);
}

main();
