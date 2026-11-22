import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fitToPages, printRecipes } from '../src/lib/print'

const recipe = (n) => ({
  title: 'Stew',
  method: 'stovetop-oven',
  servings_text: '4',
  ingredients: Array.from({ length: n }, (_, i) => ({ group: 'Produce', item: `Item ${i}`, amount: `${i} cups` })),
  steps: ['Cook it.'],
})

// jsdom does no layout: pretend a page is tall in proportion to its font size, and shorter in
// the compact layout.
function fakeHeight(page, normalAt15, compactAt15) {
  Object.defineProperty(page, 'scrollHeight', {
    configurable: true,
    get: () => (parseFloat(page.style.fontSize || '15') / 15) * (page.classList.contains('compact') ? compactAt15 : normalAt15),
  })
}

describe('printing', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="print-area"></div>'
    window.print = vi.fn()
  })

  it('renders a compact ingredients table only for long lists', () => {
    printRecipes([recipe(10), recipe(3)])
    const pages = document.querySelectorAll('#print-area .recipe-page')
    expect(pages[0].querySelector('.ing-compact')).not.toBeNull()
    expect(pages[1].querySelector('.ing-compact')).toBeNull()
    expect(window.print).toHaveBeenCalled()
  })

  it('keeps a recipe that fits at full size, shrinks one that does not, and goes compact before small print', () => {
    const area = document.getElementById('print-area')
    area.innerHTML = '<div class="recipe-page a"></div><div class="recipe-page b"><table class="ing-compact"></table></div>'
    const [a, b] = area.querySelectorAll('.recipe-page')
    fakeHeight(a, 900, 900) // fits at 15px
    fakeHeight(b, 1400, 1000) // too tall normally; compact at 14px fits
    fitToPages(area, 936)
    expect(a.style.fontSize).toBe('15px')
    expect(a.classList.contains('compact')).toBe(false)
    expect(b.classList.contains('compact')).toBe(true)
    expect(b.style.fontSize).toBe('14px')
    expect(area.classList.contains('measuring')).toBe(false)
  })
})
