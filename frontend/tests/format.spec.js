import { describe, expect, it } from 'vitest'
import { inlineMd, scaleAmount } from '@/lib/format'
import { bookmarkletHref, loader } from '@/lib/cartLoader'

describe('scaleAmount', () => {
  it('scales the leading number and keeps the rest', () => {
    expect(scaleAmount('1 lb', 1.5)).toBe('1½ lb')
    expect(scaleAmount('½ cup', 2)).toBe('1 cup')
    expect(scaleAmount('2–3 cloves', 2)).toBe('4–6 cloves')
    expect(scaleAmount('to taste', 2)).toBe('to taste')
    expect(scaleAmount('12 oz', 1)).toBe('12 oz')
  })
})

describe('inlineMd', () => {
  it('renders bold and escapes HTML', () => {
    expect(inlineMd('**Brown** – <b>x</b>')).toBe('<strong>Brown</strong> – &lt;b&gt;x&lt;/b&gt;')
  })
})

describe('cart loader bookmarklet', () => {
  it('is a javascript: URL that embeds the site address', () => {
    const href = bookmarkletHref('https://cookbook.markcheli.com')
    expect(href.startsWith('javascript:(')).toBe(true)
    expect(decodeURIComponent(href)).toContain('"https://cookbook.markcheli.com"')
    expect(decodeURIComponent(href)).toContain('freshAddToCartButton')
  })
  it('refuses to run anywhere but amazon.com', () => {
    const alerts = []
    globalThis.alert = (m) => alerts.push(m)
    loader('https://cookbook.markcheli.com')
    expect(alerts[0]).toMatch(/amazon\.com/)
  })
})
