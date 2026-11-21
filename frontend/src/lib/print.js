import { inlineMd, scaleAmount } from './format'
import { methods } from '@/api'

/**
 * Print cooking instructions from this page, not a pop-up: an iPhone Home Screen web app has no
 * pop-up windows. The layout is the original site's: title, meta line, ingredients table,
 * numbered steps, one recipe per page. #print-area is emptied once the print dialog closes.
 */
export function printRecipes(recipes) {
  const area = document.getElementById('print-area')
  if (!area || !recipes.length) return
  area.innerHTML = recipes
    .map((r, index) => {
      const factor = r.factor ?? 1
      const meta = [
        `<strong>${methods[r.method] ?? r.method}</strong>`,
        r.servings_text ? `${r.servings_text} servings${factor !== 1 ? ` (×${factor})` : ''}` : '',
        r.prep_text ? `Prep: ${r.prep_text}` : '',
        r.cook_text ? `Cook: ${r.cook_text}` : '',
      ].filter(Boolean)
      const rows = r.ingredients
        .map((i) => `<tr><td>${inlineMd(i.group || '')}</td><td>${inlineMd(i.item)}</td><td>${inlineMd(scaleAmount(i.amount, factor) || '')}</td></tr>`)
        .join('')
      const steps = r.steps.map((s) => `<li>${inlineMd(s)}</li>`).join('')
      return `
        <div class="recipe-page${index < recipes.length - 1 ? ' page-break' : ''}">
          <h1>${inlineMd(r.title)}</h1>
          <div class="meta">${meta.join(' | ')}</div>
          <h2>Ingredients</h2>
          <table class="ingredients-table"><thead><tr><th>Category</th><th>Item</th><th>Amount</th></tr></thead><tbody>${rows}</tbody></table>
          <h2>Instructions</h2>
          <ol class="method-steps">${steps}</ol>
        </div>`
    })
    .join('')
  const clear = () => {
    area.innerHTML = ''
    window.removeEventListener('afterprint', clear)
  }
  window.addEventListener('afterprint', clear)
  window.print()
}
