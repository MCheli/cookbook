import { inlineMd, scaleAmount } from './format'
import { methods } from '@/api'

/**
 * Print cooking instructions from this page, not a pop-up: an iPhone Home Screen web app has no
 * pop-up windows. The layout is the original site's: title, meta line, ingredients table,
 * numbered steps, one recipe per page. Each recipe is fitted to its page first (fitToPages).
 * #print-area is emptied once the print dialog closes.
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
      const cells = r.ingredients.map((i) => [inlineMd(i.group || ''), inlineMd(i.item), inlineMd(scaleAmount(i.amount, factor) || '')])
      const rows = cells.map((c) => `<tr><td>${c[0]}</td><td>${c[1]}</td><td>${c[2]}</td></tr>`).join('')
      // Compact layout for long lists: Item | Amount twice across, no category (fitToPages picks it).
      const half = Math.ceil(cells.length / 2)
      const paired = cells
        .slice(0, half)
        .map((c, n) => {
          const o = cells[half + n] || ['', '', '']
          return `<tr><td>${c[1]}</td><td>${c[2]}</td><td class="pair">${o[1]}</td><td>${o[2]}</td></tr>`
        })
        .join('')
      const compactTable =
        cells.length >= 8
          ? `<table class="ingredients-table ing-compact"><thead><tr><th>Item</th><th>Amount</th><th class="pair">Item</th><th>Amount</th></tr></thead><tbody>${paired}</tbody></table>`
          : ''
      const steps = r.steps.map((s) => `<li>${inlineMd(s)}</li>`).join('')
      return `
        <div class="recipe-page${index < recipes.length - 1 ? ' page-break' : ''}">
          <h1>${inlineMd(r.title)}</h1>
          <div class="meta">${meta.join(' | ')}</div>
          <h2>Ingredients</h2>
          <table class="ingredients-table ing-normal"><thead><tr><th>Category</th><th>Item</th><th>Amount</th></tr></thead><tbody>${rows}</tbody></table>${compactTable}
          <h2>Instructions</h2>
          <ol class="method-steps">${steps}</ol>
        </div>`
    })
    .join('')
  fitToPages(area)
  const clear = () => {
    area.innerHTML = ''
    window.removeEventListener('afterprint', clear)
  }
  window.addEventListener('afterprint', clear)
  window.print()
}

// The printable area of a US Letter page with the 0.5in margins in main.css, in CSS px (96/in).
// A little under 10in tall, so browser rounding and the print header never push a line over.
export const PAGE_HEIGHT_PX = 9.75 * 96
// Tried in order until the recipe fits: the normal layout a little smaller, then the compact one
// (two-column ingredients, when the list is long enough to have one) from full size down.
const NORMAL_SIZES = [15, 14, 13]
const COMPACT_SIZES = [15, 14, 13, 12.5, 12, 11.5, 11, 10.5, 10, 9.5, 9]

/**
 * One recipe, one page: lay the pages out off-screen at the printed width and, for any that run
 * long, step down through NORMAL_SIZES and then COMPACT_SIZES (every print size is in em) until
 * it fits. Stops at 9px; a recipe longer than that prints on two pages rather than unreadably.
 */
export function fitToPages(area, pageHeight = PAGE_HEIGHT_PX) {
  area.classList.add('measuring')
  try {
    for (const page of area.querySelectorAll('.recipe-page')) {
      const hasCompact = !!page.querySelector('.ing-compact')
      const attempts = [...NORMAL_SIZES.map((px) => [false, px]), ...(hasCompact ? COMPACT_SIZES : COMPACT_SIZES.slice(3)).map((px) => [hasCompact, px])]
      for (const [compact, px] of attempts) {
        page.classList.toggle('compact', compact)
        page.style.fontSize = `${px}px`
        if (page.scrollHeight <= pageHeight) break
      }
    }
  } finally {
    area.classList.remove('measuring')
  }
}
