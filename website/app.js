// State
let selectedRecipes = new Set();
let currentFilter = 'all';

// Fisher-Yates shuffle algorithm
function shuffleArray(array) {
  const shuffled = [...array];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
}

// Helper: Convert markdown bold (**text**) to HTML
function formatText(text) {
  return text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
}

// DOM Elements
const recipeGrid = document.getElementById('recipe-grid');
const recipesSection = document.getElementById('recipes-section');
const grocerySection = document.getElementById('grocery-section');
const selectedCount = document.getElementById('selected-count');
const generateListBtn = document.getElementById('generate-list');
const clearSelectionBtn = document.getElementById('clear-selection');
const backToRecipesBtn = document.getElementById('back-to-recipes');
const printInstructionsBtn = document.getElementById('print-instructions');
const filterButtons = document.querySelectorAll('.filter-btn');
const modal = document.getElementById('recipe-modal');
const modalBody = document.getElementById('modal-body');
const modalClose = document.querySelector('.modal-close');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  renderRecipes();
  setupEventListeners();
});

function setupEventListeners() {
  generateListBtn.addEventListener('click', generateGroceryList);
  clearSelectionBtn.addEventListener('click', clearSelection);
  backToRecipesBtn.addEventListener('click', showRecipes);
  printInstructionsBtn.addEventListener('click', printCookingInstructions);
  modalClose.addEventListener('click', closeModal);
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
  });

  filterButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      currentFilter = btn.dataset.category;
      filterButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderRecipes();
    });
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
  });
}

function renderRecipes() {
  const filteredRecipes = currentFilter === 'all'
    ? RECIPES
    : RECIPES.filter(r => r.category === currentFilter);

  const shuffledRecipes = shuffleArray(filteredRecipes);

  recipeGrid.innerHTML = shuffledRecipes.map(recipe => `
    <div class="recipe-card ${selectedRecipes.has(recipe.id) ? 'selected' : ''}"
         data-id="${recipe.id}">
      <div class="checkbox"></div>
      <span class="category">${recipe.category}</span>
      <h3>${recipe.title}</h3>
      <div class="meta">
        ${recipe.servings ? `${recipe.servings} servings` : ''}
        ${recipe.prepTime ? `| Prep: ${recipe.prepTime}` : ''}
        ${recipe.cookTime ? `| Cook: ${recipe.cookTime}` : ''}
      </div>
      <span class="view-details" data-action="details">View Recipe</span>
    </div>
  `).join('');

  // Add click handlers
  recipeGrid.querySelectorAll('.recipe-card').forEach(card => {
    card.addEventListener('click', (e) => {
      if (e.target.dataset.action === 'details') {
        e.stopPropagation();
        showRecipeDetails(card.dataset.id);
      } else {
        toggleRecipeSelection(card.dataset.id);
      }
    });
  });
}

function toggleRecipeSelection(id) {
  if (selectedRecipes.has(id)) {
    selectedRecipes.delete(id);
  } else {
    selectedRecipes.add(id);
  }
  updateSelectionUI();
}

function updateSelectionUI() {
  selectedCount.textContent = selectedRecipes.size;

  recipeGrid.querySelectorAll('.recipe-card').forEach(card => {
    if (selectedRecipes.has(card.dataset.id)) {
      card.classList.add('selected');
    } else {
      card.classList.remove('selected');
    }
  });
}

function clearSelection() {
  selectedRecipes.clear();
  updateSelectionUI();
}

function showRecipeDetails(id) {
  const recipe = RECIPES.find(r => r.id === id);
  if (!recipe) return;

  const isSelected = selectedRecipes.has(id);

  modalBody.innerHTML = `
    <h2>${recipe.title}</h2>
    <div class="meta">
      <strong>${recipe.category}</strong>
      ${recipe.servings ? ` | ${recipe.servings} servings` : ''}
      ${recipe.prepTime ? ` | Prep: ${recipe.prepTime}` : ''}
      ${recipe.cookTime ? ` | Cook: ${recipe.cookTime}` : ''}
    </div>

    <h3>Ingredients</h3>
    <table class="ingredients-table">
      <thead>
        <tr>
          <th>Category</th>
          <th>Item</th>
          <th>Amount</th>
        </tr>
      </thead>
      <tbody>
        ${recipe.ingredients.map(ing => `
          <tr>
            <td>${ing.group || ''}</td>
            <td>${ing.item}</td>
            <td>${ing.amount}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>

    <h3>Method</h3>
    <ol class="method-steps">
      ${recipe.method.map(step => `<li>${formatText(step)}</li>`).join('')}
    </ol>

    <div class="modal-actions">
      <button class="btn ${isSelected ? 'btn-secondary' : 'btn-primary'}" id="modal-select-btn">
        ${isSelected ? 'Remove from Selection' : 'Add to Selection'}
      </button>
    </div>
  `;

  document.getElementById('modal-select-btn').addEventListener('click', () => {
    toggleRecipeSelection(id);
    const newIsSelected = selectedRecipes.has(id);
    const btn = document.getElementById('modal-select-btn');
    btn.textContent = newIsSelected ? 'Remove from Selection' : 'Add to Selection';
    btn.className = `btn ${newIsSelected ? 'btn-secondary' : 'btn-primary'}`;
  });

  modal.classList.remove('hidden');
}

function closeModal() {
  modal.classList.add('hidden');
}

function generateGroceryList() {
  if (selectedRecipes.size === 0) {
    alert('Please select at least one recipe');
    return;
  }

  const selectedRecipesList = document.getElementById('selected-recipes-list');
  const groceryListContainer = document.getElementById('grocery-list');

  // Get selected recipe objects
  const recipes = RECIPES.filter(r => selectedRecipes.has(r.id));

  // Display selected recipe names
  selectedRecipesList.innerHTML = recipes.map(r => `<li>${r.title}</li>`).join('');

  // Combine and organize ingredients
  const groceryItems = combineIngredients(recipes);

  // Group by category
  const categories = groupByCategory(groceryItems);

  // Render grocery list
  groceryListContainer.innerHTML = Object.entries(categories).map(([category, items]) => `
    <div class="grocery-category">
      <h3>${category || 'Other'}</h3>
      ${items.map(item => `
        <div class="grocery-item">
          <div class="item-info">
            <div class="item-name">${item.name}</div>
            <div class="item-amount">${item.amounts.join(' + ')}</div>
          </div>
          <a href="${generateAmazonUrl(item.name)}" target="_blank" class="amazon-link">
            Whole Foods
          </a>
        </div>
      `).join('')}
    </div>
  `).join('');

  // Show grocery section
  recipesSection.classList.add('hidden');
  grocerySection.classList.remove('hidden');
}

function combineIngredients(recipes) {
  const combined = new Map();

  for (const recipe of recipes) {
    for (const ing of recipe.ingredients) {
      // Normalize the item name for combining
      const normalizedName = normalizeIngredientName(ing.item);
      const key = `${normalizedName}|${ing.group}`;

      if (combined.has(key)) {
        const existing = combined.get(key);
        if (ing.amount && !existing.amounts.includes(ing.amount)) {
          existing.amounts.push(ing.amount);
        }
      } else {
        combined.set(key, {
          name: ing.item,
          normalizedName: normalizedName,
          category: ing.group,
          amounts: ing.amount ? [ing.amount] : []
        });
      }
    }
  }

  return Array.from(combined.values());
}

function normalizeIngredientName(name) {
  return name.toLowerCase()
    .replace(/\s*\(.*?\)\s*/g, '') // Remove parenthetical notes
    .replace(/,.*$/, '') // Remove anything after comma
    .trim();
}

function groupByCategory(items) {
  const categories = {};

  // Define category order
  const categoryOrder = [
    'Protein',
    'Vegetables',
    'Produce',
    'Dairy',
    'Grains',
    'Pantry',
    'Seasoning',
    'Spices',
    'Liquids',
    'Sauce',
    'Other'
  ];

  for (const item of items) {
    const category = item.category || 'Other';
    if (!categories[category]) {
      categories[category] = [];
    }
    categories[category].push(item);
  }

  // Sort items within each category alphabetically
  for (const category of Object.keys(categories)) {
    categories[category].sort((a, b) => a.name.localeCompare(b.name));
  }

  // Return in preferred order
  const ordered = {};
  for (const cat of categoryOrder) {
    if (categories[cat]) {
      ordered[cat] = categories[cat];
      delete categories[cat];
    }
  }

  // Add any remaining categories
  for (const [cat, items] of Object.entries(categories)) {
    ordered[cat] = items;
  }

  return ordered;
}

function generateAmazonUrl(itemName) {
  // Clean up the item name for searching
  const searchTerm = itemName
    .replace(/\s*\(.*?\)\s*/g, ' ') // Remove parenthetical notes
    .replace(/,.*$/, '') // Remove anything after comma
    .replace(/\s+/g, ' ') // Normalize whitespace
    .trim();

  // Generate Amazon Whole Foods search URL
  const encoded = encodeURIComponent(searchTerm);
  return `https://www.amazon.com/s?k=${encoded}&i=wholefoods`;
}

function showRecipes() {
  grocerySection.classList.add('hidden');
  recipesSection.classList.remove('hidden');
}

function printCookingInstructions() {
  const recipes = RECIPES.filter(r => selectedRecipes.has(r.id));

  if (recipes.length === 0) {
    alert('No recipes selected');
    return;
  }

  const printContent = recipes.map((recipe, index) => `
    <div class="recipe-page${index < recipes.length - 1 ? ' page-break' : ''}">
      <h1>${recipe.title}</h1>
      <div class="meta">
        <strong>${recipe.category}</strong>
        ${recipe.servings ? ` | ${recipe.servings} servings` : ''}
        ${recipe.prepTime ? ` | Prep: ${recipe.prepTime}` : ''}
        ${recipe.cookTime ? ` | Cook: ${recipe.cookTime}` : ''}
      </div>

      <h2>Ingredients</h2>
      <table class="ingredients-table">
        <thead>
          <tr>
            <th>Category</th>
            <th>Item</th>
            <th>Amount</th>
          </tr>
        </thead>
        <tbody>
          ${recipe.ingredients.map(ing => `
            <tr>
              <td>${ing.group || ''}</td>
              <td>${ing.item}</td>
              <td>${ing.amount}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>

      <h2>Instructions</h2>
      <ol class="method-steps">
        ${recipe.method.map(step => `<li>${formatText(step)}</li>`).join('')}
      </ol>
    </div>
  `).join('');

  const printWindow = window.open('', '_blank');
  printWindow.document.write(`
    <!DOCTYPE html>
    <html>
    <head>
      <title>Cooking Instructions</title>
      <style>
        * {
          box-sizing: border-box;
          margin: 0;
          padding: 0;
        }
        body {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          line-height: 1.6;
          padding: 2rem;
          color: #333;
        }
        .recipe-page {
          max-width: 800px;
          margin: 0 auto;
        }
        .page-break {
          page-break-after: always;
        }
        h1 {
          font-size: 1.75rem;
          margin-bottom: 0.5rem;
          color: #2d5a27;
        }
        h2 {
          font-size: 1.25rem;
          margin: 1.5rem 0 1rem;
          color: #2d5a27;
        }
        .meta {
          color: #666;
          margin-bottom: 1rem;
          font-size: 0.9rem;
        }
        .ingredients-table {
          width: 100%;
          border-collapse: collapse;
          margin-bottom: 1rem;
        }
        .ingredients-table th,
        .ingredients-table td {
          padding: 0.5rem;
          text-align: left;
          border-bottom: 1px solid #ddd;
        }
        .ingredients-table th {
          background: #f5f5f5;
          font-weight: 600;
        }
        .method-steps {
          padding-left: 1.5rem;
        }
        .method-steps li {
          margin-bottom: 0.75rem;
        }
        @media print {
          body {
            padding: 0;
          }
          .page-break {
            page-break-after: always;
          }
        }
      </style>
    </head>
    <body>
      ${printContent}
    </body>
    </html>
  `);
  printWindow.document.close();
  printWindow.focus();
  printWindow.print();
}
