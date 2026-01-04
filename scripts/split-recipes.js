#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const RECIPE_FILES = [
  { file: 'instapot.md', folder: 'instapot' },
  { file: 'crockpot.md', folder: 'crockpot' },
  { file: 'stovetop-oven.md', folder: 'stovetop-oven' }
];

function slugify(title) {
  return title
    .toLowerCase()
    .replace(/[^\w\s-]/g, '') // Remove special chars except spaces and hyphens
    .replace(/\s+/g, '-')      // Replace spaces with hyphens
    .replace(/-+/g, '-')       // Replace multiple hyphens with single
    .replace(/^-+|-+$/g, '')   // Remove leading/trailing hyphens
    .trim();
}

function splitRecipes(content) {
  const recipes = [];

  // Split by ## headers (recipe titles)
  const sections = content.split(/^## /gm);

  for (const section of sections) {
    if (!section.trim()) continue;

    const lines = section.split('\n');
    const titleLine = lines[0].trim();

    // Skip main header (starts with #) or empty
    if (titleLine.startsWith('#') || !titleLine) continue;

    // Extract title without emoji for filename
    const titleForFile = titleLine.replace(/^[\u{1F300}-\u{1F9FF}]\s*/u, '').trim();
    const slug = slugify(titleForFile);

    if (!slug) continue;

    // Reconstruct the recipe content with the ## header
    let recipeContent = `## ${titleLine}\n${lines.slice(1).join('\n')}`;

    // Remove trailing --- separator if present
    recipeContent = recipeContent.replace(/\n---\s*$/, '').trim();

    recipes.push({
      slug,
      title: titleForFile,
      content: recipeContent
    });
  }

  return recipes;
}

function main() {
  const baseDir = path.join(__dirname, '..');
  const recipesDir = path.join(baseDir, 'recipes');

  // Ensure recipes directory exists
  if (!fs.existsSync(recipesDir)) {
    fs.mkdirSync(recipesDir);
  }

  let totalRecipes = 0;

  for (const { file, folder } of RECIPE_FILES) {
    const inputPath = path.join(baseDir, file);
    const outputDir = path.join(recipesDir, folder);

    if (!fs.existsSync(inputPath)) {
      console.log(`Skipping ${file} (not found)`);
      continue;
    }

    // Ensure output directory exists
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }

    const content = fs.readFileSync(inputPath, 'utf-8');
    const recipes = splitRecipes(content);

    for (const recipe of recipes) {
      const outputPath = path.join(outputDir, `${recipe.slug}.md`);
      fs.writeFileSync(outputPath, recipe.content + '\n');
      console.log(`  Created: recipes/${folder}/${recipe.slug}.md`);
    }

    console.log(`Split ${recipes.length} recipes from ${file} into recipes/${folder}/`);
    totalRecipes += recipes.length;
  }

  console.log(`\nTotal: ${totalRecipes} recipe files created`);
}

main();
