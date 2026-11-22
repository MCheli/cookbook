import { describe, expect, it } from 'vitest'
import { bookmarkletHref } from '../src/lib/cartLoader'

describe('cart bookmarklet', () => {
  it('is a javascript: URL that parses, with the site baked in', () => {
    const href = bookmarkletHref('https://cookbook.example.com')
    expect(href.startsWith('javascript:(')).toBe(true)
    const code = decodeURIComponent(href.slice('javascript:'.length))
    expect(() => new Function(code)).not.toThrow()
    expect(code).toContain('"https://cookbook.example.com"')
    // It reads the cart first and steps quantities with the cart's + button.
    expect(code).toContain('qs-widget-increment-decl')
    expect(code).toContain('/list?in_cart=')
  })
})
