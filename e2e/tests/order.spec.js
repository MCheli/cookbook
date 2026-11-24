import { expect, test } from '@playwright/test'

// The order flow as a cook uses it on a phone: pick recipes, fill the Whole Foods cart item by
// item, print, mark the order placed, start another. Runs against a fresh local stack with the
// dev password user (run.sh). Nothing here reaches Amazon: its pages are stubbed.

const EMAIL = process.env.E2E_EMAIL || 'dev@cookbook.local'
const PASSWORD = process.env.E2E_PASSWORD || 'dev-password'
const PASTA = 'pasta-with-sausage-cream-sauce'
const SHRIMP = 'garlic-butter-shrimp'

const shot = (page, testInfo, name) =>
  page.screenshot({ path: `screenshots/${testInfo.project.name}-${name}.png`, fullPage: true })
const isPhone = (testInfo) => testInfo.project.name !== 'desktop'

test.beforeEach(async ({ context, page }) => {
  await context.route(/https:\/\/(www\.)?amazon\.com\/.*/, (route) =>
    route.fulfill({ contentType: 'text/html', body: '<html><body><h1>Amazon (stub)</h1></body></html>' }),
  )
  // Record every print: whether it ran inside the tap (iOS ignores it otherwise) and what it held.
  await context.addInitScript(() => {
    window.__prints = []
    window.__inClick = false
    window.addEventListener('click', () => (window.__inClick = true), true)
    window.addEventListener('click', () => (window.__inClick = false), false)
    window.print = () =>
      window.__prints.push({
        inClick: window.__inClick,
        activation: navigator.userActivation ? navigator.userActivation.isActive : null,
        titles: [...document.querySelectorAll('#print-area .recipe-page h1')].map((h) => h.textContent),
      })
  })
  const r = await page.request.post('/api/auth/login', { data: { email: EMAIL, password: PASSWORD } })
  expect(r.ok()).toBeTruthy()
  await page.request.post('/api/lists/current/clear')
})

async function recipe(page, slug) {
  return (await page.request.get(`/api/recipes/${slug}`)).json()
}
async function addToOrder(page, slug, factor = 1) {
  const r = await recipe(page, slug)
  await page.request.post('/api/lists/current/recipes', { data: { recipe_id: r.id, servings_factor: factor } })
  return r
}
async function noSideScroll(page) {
  const [scroll, client] = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth])
  expect(scroll, 'page scrolls sideways').toBeLessThanOrEqual(client + 1)
}
const prints = (page) => page.evaluate(() => window.__prints)

test('pick recipes and build an order', async ({ page }, testInfo) => {
  const pasta = await recipe(page, PASTA)
  const shrimp = await recipe(page, SHRIMP)
  await page.goto('/')
  await page.getByRole('button', { name: new RegExp(pasta.title) }).first().click()
  await page.getByRole('button', { name: new RegExp(shrimp.title) }).first().click()
  if (isPhone(testInfo)) {
    const bar = page.getByTestId('selection-bar')
    await expect(bar).toBeVisible()
    await shot(page, testInfo, 'home-selected')
    await bar.getByRole('button', { name: 'Add to order (2)' }).click()
  } else {
    await page.getByRole('button', { name: 'Add to order (2)' }).click()
  }
  await expect(page).toHaveURL(/\/list$/)
  await expect(page.getByRole('heading', { name: 'Current order' })).toBeVisible()
  await expect(page.getByTestId('order-started')).toContainText('2 recipes')
  await expect(page.getByText(pasta.title).first()).toBeVisible()
  await expect(page.getByText(/add all .* at once/i)).toHaveCount(0)
  await expect(page.getByText(/this week/i)).toHaveCount(0)
  await noSideScroll(page)
  await shot(page, testInfo, 'order')
})

test('Whole Foods buttons open the store and never tick an item by themselves', async ({ page, context }, testInfo) => {
  await page.request.post('/api/products', { data: { asin: 'B0TESTSAUS', title: 'Italian sausage links, 1 lb', match_keys: ['Italian sausage links'] } })
  await addToOrder(page, PASTA)
  await page.goto('/list')
  const row = page.getByTestId('item-italian sausage links')
  await expect(row).toBeVisible()
  const progress = page.getByTestId('cart-progress')
  await expect(progress).toContainText(/^0 of \d+ in your cart\s*$/)

  const [store] = await Promise.all([context.waitForEvent('page'), row.getByTestId('open-wf').click()])
  await store.close()
  // Opening the store page only highlights the box to tick.
  await expect(row.getByTestId('in-cart')).toHaveText(/☐ In cart/)
  await expect(progress).toContainText(/^0 of/)
  await shot(page, testInfo, 'after-opening-store')

  await row.getByTestId('in-cart').click()
  await expect(row.getByTestId('in-cart')).toHaveText(/✓ In cart/)
  await expect(progress).toContainText(/^1 of/)
  await row.getByTestId('in-cart').click() // a mistaken tick comes off with one tap
  await expect(row.getByTestId('in-cart')).toHaveText(/☐ In cart/)
  await expect(progress).toContainText(/^0 of/)

  // An item with no product searches Whole Foods instead.
  const unmatched = page.getByTestId('open-wf').filter({ hasText: 'Find on Whole Foods' }).first()
  await expect(unmatched).toBeVisible()

  // "have it" takes an item off what's left to buy.
  const need = Number((await progress.textContent()).match(/of (\d+)/)[1])
  await row.getByTestId('have-it').click()
  await expect(progress).toContainText(`of ${need - 1}`)
  await page.getByLabel('Show items I have').check()
  await expect(row.getByRole('button', { name: 'Need it after all' })).toBeVisible()
  await row.getByRole('button', { name: 'Need it after all' }).click()
  await expect(progress).toContainText(`of ${need}`)
  await noSideScroll(page)
})

test('printing runs straight from the tap: order, recipe page, last order and history', async ({ page }) => {
  const pasta = await addToOrder(page, PASTA, 2)
  const shrimp = await addToOrder(page, SHRIMP)
  await page.goto('/list')
  const printBtn = page.getByTestId('print')
  await expect(printBtn).toHaveText('Print recipes')
  await expect(printBtn).toBeEnabled()
  await printBtn.click()
  let p = await prints(page)
  expect(p).toHaveLength(1)
  expect(p[0].inClick).toBe(true)
  if (p[0].activation !== null) expect(p[0].activation).toBe(true)
  expect(p[0].titles).toEqual([pasta.title, shrimp.title])

  await page.goto(`/r/${PASTA}`)
  await page.getByRole('button', { name: 'Print', exact: true }).click()
  p = await prints(page)
  expect(p.at(-1).inClick).toBe(true)
  expect(p.at(-1).titles).toEqual([pasta.title])
  // Leaving the page empties the print area, so the browser's own Print prints what's shown.
  await page.getByRole('link', { name: 'Cookbook' }).first().click()
  await expect.poll(() => page.evaluate(() => document.getElementById('print-area').innerHTML)).toBe('')

  // After placing the order, its recipes still print from the new order's page and from History.
  await page.request.post('/api/lists/current/complete')
  await page.goto('/list')
  const last = page.getByTestId('last-order')
  await expect(last).toContainText(pasta.title)
  await expect(page.getByTestId('print-last')).toBeEnabled()
  await page.getByTestId('print-last').click()
  p = await prints(page)
  expect(p.at(-1).inClick).toBe(true)
  expect(p.at(-1).titles).toEqual([pasta.title, shrimp.title])

  await page.goto('/history')
  const first = page.getByTestId('past-order').first()
  await expect(first).toContainText(pasta.title)
  await first.getByRole('button', { name: 'Print recipes' }).click()
  p = await prints(page)
  expect(p.at(-1).inClick).toBe(true)
  expect(p.at(-1).titles).toEqual([pasta.title, shrimp.title])
})

test('placing an order, undoing a mistaken one, and a second order the same day', async ({ page }, testInfo) => {
  const pasta = await addToOrder(page, PASTA)
  const shrimp = await recipe(page, SHRIMP)
  await page.goto('/list')
  const place = page.getByTestId('place-order')

  // A stray tap only asks.
  await place.getByTestId('placed').click()
  await expect(place).toContainText('Move this order to History and start a new one?')
  await shot(page, testInfo, 'confirm-placed')
  await place.getByRole('button', { name: 'Not yet' }).click()
  await expect(page.getByText(pasta.title).first()).toBeVisible()
  await expect(page.getByTestId('empty-order')).toHaveCount(0)

  await place.getByTestId('placed').click()
  await place.getByTestId('confirm-placed').click()
  await expect(page.getByTestId('empty-order')).toBeVisible()
  await expect(page.getByTestId('last-order')).toContainText(pasta.title)
  await noSideScroll(page)
  await shot(page, testInfo, 'new-empty-order')

  // Marked placed by mistake: reopen it.
  await page.getByTestId('reopen').click()
  await expect(page.getByTestId('order-started')).toContainText('1 recipe')
  await expect(page.getByText(pasta.title).first()).toBeVisible()

  // Place it for real, then start a second order the same day from a recipe page.
  await page.getByTestId('placed').click()
  await page.getByTestId('confirm-placed').click()
  await expect(page.getByTestId('empty-order')).toBeVisible()
  await page.goto(`/r/${SHRIMP}`)
  await page.getByRole('button', { name: 'Add to order' }).click()
  await expect(page.getByRole('button', { name: '✓ In your order' })).toBeVisible()
  await page.goto('/list')
  await expect(page.getByTestId('order-started')).toContainText('1 recipe')
  await expect(page.getByText(shrimp.title).first()).toBeVisible()
  await expect(page.getByText(pasta.title)).toHaveCount(0)
  await page.getByTestId('placed').click()
  await page.getByTestId('confirm-placed').click()
  await expect(page.getByTestId('empty-order')).toBeVisible() // placed for sure before leaving

  await page.goto('/history')
  const orders = page.getByTestId('past-order')
  await expect(orders.nth(0)).toContainText(shrimp.title)
  await expect(orders.nth(1)).toContainText(pasta.title)
  await noSideScroll(page)
  await shot(page, testInfo, 'history')
})

test('every signed-in page fits the screen', async ({ page }, testInfo) => {
  await addToOrder(page, PASTA)
  for (const [name, path] of [
    ['home', '/'],
    ['order-full', '/list'],
    ['recipe', `/r/${PASTA}`],
    ['history-page', '/history'],
    ['products', '/products'],
    ['settings', '/settings'],
  ]) {
    await page.goto(path)
    await page.waitForLoadState('networkidle')
    await noSideScroll(page)
    await shot(page, testInfo, `page-${name}`)
  }
  if (isPhone(testInfo)) {
    await page.goto('/list')
    await page.getByRole('button', { name: 'Menu' }).click()
    await expect(page.getByRole('link', { name: /^Order/ })).toBeVisible()
    await shot(page, testInfo, 'menu')
  }
})

// The iPhone Home Screen app: print() does nothing there and a PDF opens in a bare viewer, so
// Print hands the recipes' PDF to the share sheet (Print, Save to Files), from the tap.
test('in the Home Screen app, Print opens the share sheet with the PDF', async ({ page, context }, testInfo) => {
  test.skip(testInfo.project.name !== 'iphone', 'Home Screen apps are an iPhone thing')
  await context.addInitScript(() => {
    Object.defineProperty(navigator, 'standalone', { value: true, configurable: true })
    window.__shares = []
    navigator.canShare = (data) => !!data?.files?.length
    navigator.share = (data) => {
      const f = data.files[0]
      window.__shares.push({ inClick: window.__inClick, name: f.name, type: f.type, size: f.size })
      return Promise.resolve()
    }
  })
  const shares = () => page.evaluate(() => window.__shares)
  const pasta = await addToOrder(page, PASTA, 2)
  await addToOrder(page, SHRIMP)

  // The PDF is fetched ahead of the tap; wait for it (listening before the page loads).
  const pdfFor = (part) => page.waitForResponse((r) => r.url().includes(part) && r.ok())
  let ready = pdfFor('/api/recipes/pdf')
  await page.goto('/list')
  const printBtn = page.getByTestId('print')
  await expect(printBtn).toHaveText('Print or save')
  await expect(page.getByRole('link', { name: 'PDF' })).toHaveCount(0)
  await ready
  await page.waitForTimeout(200)
  await printBtn.click()
  let s = await shares()
  expect(s).toHaveLength(1)
  expect(s[0]).toMatchObject({ inClick: true, name: 'recipes.pdf', type: 'application/pdf' })
  expect(s[0].size).toBeGreaterThan(1000)
  expect(await prints(page)).toHaveLength(0)
  await shot(page, testInfo, 'homescreen-order')

  ready = pdfFor(`/api/recipes/${PASTA}/pdf`)
  await page.goto(`/r/${PASTA}`)
  await ready
  await page.waitForTimeout(200)
  await page.getByRole('button', { name: 'Print or save' }).click()
  s = await shares()
  expect(s.at(-1)).toMatchObject({ inClick: true, type: 'application/pdf' })

  await page.request.post('/api/lists/current/complete')
  ready = pdfFor('/api/recipes/pdf')
  await page.goto('/history')
  const first = page.getByTestId('past-order').first()
  await expect(first).toContainText(pasta.title)
  await ready
  await page.waitForTimeout(200)
  await first.getByRole('button', { name: 'Print recipes' }).click()
  s = await shares()
  expect(s.at(-1)).toMatchObject({ inClick: true, type: 'application/pdf' })
  expect(await prints(page)).toHaveLength(0)
})
