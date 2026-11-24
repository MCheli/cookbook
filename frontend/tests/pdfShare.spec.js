import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// Fresh module each test: it keeps fetched PDFs in a module-level cache.
async function load() {
  vi.resetModules()
  return import('../src/lib/pdfShare')
}

const flush = () => new Promise((r) => setTimeout(r, 0))

describe('pdfUrlFor', () => {
  it('names each recipe and its scale, and leaves factors off when nothing is scaled', async () => {
    const { pdfUrlFor } = await load()
    expect(pdfUrlFor([{ slug: 'a', factor: 1 }, { slug: 'b', factor: 1 }])).toBe('/api/recipes/pdf?slugs=a,b')
    expect(pdfUrlFor([{ slug: 'a', factor: 2 }, { slug: 'b', servings_factor: 1 }])).toBe('/api/recipes/pdf?slugs=a,b&factors=2,1')
    expect(pdfUrlFor([])).toBeNull()
  })
})

describe('sharePdf', () => {
  let share
  beforeEach(() => {
    share = vi.fn(() => Promise.resolve())
    navigator.share = share
    navigator.canShare = () => true
    globalThis.fetch = vi.fn(() => Promise.resolve({ ok: true, blob: () => Promise.resolve(new Blob(['%PDF'])) }))
  })
  afterEach(() => {
    delete navigator.standalone
  })

  it('does nothing outside the Home Screen app, so the page prints as usual', async () => {
    const { preparePdf, sharePdf } = await load()
    preparePdf('/api/recipes/pdf?slugs=a')
    expect(fetch).not.toHaveBeenCalled()
    expect(sharePdf('/api/recipes/pdf?slugs=a')).toBe(false)
  })

  it('in the Home Screen app, shares the PDF fetched ahead of the tap', async () => {
    navigator.standalone = true
    const { preparePdf, sharePdf } = await load()
    preparePdf('/api/recipes/pdf?slugs=a')
    await flush()
    expect(sharePdf('/api/recipes/pdf?slugs=a')).toBe(true)
    expect(share).toHaveBeenCalledTimes(1)
    const [file] = share.mock.calls[0][0].files
    expect(file.type).toBe('application/pdf')
    expect(file.name).toBe('recipes.pdf')
  })

  it('says to tap again while the PDF is still on its way, instead of failing silently', async () => {
    navigator.standalone = true
    const { sharePdf } = await load()
    const { toasts } = await import('../src/lib/toast')
    expect(sharePdf('/api/recipes/pdf?slugs=b')).toBe(true)
    expect(share).not.toHaveBeenCalled()
    expect(toasts.at(-1).message).toMatch(/tap again/i)
  })
})
