/**
 * The Whole Foods cart button: a bookmarklet that runs on amazon.com, in the cook's own signed-in
 * session. Amazon has no API for the Whole Foods cart, so this does what a person would do: open
 * each product's Whole Foods page (in a hidden frame on amazon.com) and press its add button.
 *
 * - On the cart page opened at the cart manifest's loader_url (no longer linked from the app; agents
 *   may still use it), it reads the ASINs from the URL fragment
 *   (#cookbook-cart=ASIN*qty,...), which never leaves the browser. It skips what's already in the
 *   cart, adds the rest, then presses the cart's + button until each quantity is right.
 * - On a product page, it opens the cookbook's "save product" form for that ASIN instead.
 *
 * It only ever adds to the cart. Checkout stays with the cook.
 */

function loader(SITE) {
  const BRAND = 'VUZHIFdob2xlIEZvb2Rz'
  if (!/(^|\.)amazon\.com$/.test(location.hostname)) {
    alert('Open this on a Whole Foods product page on amazon.com to save it to your Cookbook products.')
    return
  }
  const hash = location.hash.match(/cookbook-cart=([^&]+)/)
  const asinInPath = location.pathname.match(/\/(?:dp|gp\/product)\/([A-Z0-9]{10})/)
  if (!hash && asinInPath) {
    const title = (document.querySelector('#productTitle') || {}).textContent || document.title
    const priceEl = document.querySelector('#corePrice_feature_div .a-offscreen, .a-price .a-offscreen')
    const q = new URLSearchParams({ asin: asinInPath[1], title: title.trim().slice(0, 300), price: priceEl ? priceEl.textContent.trim() : '' })
    window.open(SITE + '/products?add=1&' + q.toString(), '_blank')
    return
  }
  if (!hash) {
    alert('Open this on a Whole Foods product page to save it to your Cookbook products.')
    return
  }
  const items = decodeURIComponent(hash[1])
    .split(',')
    .map((p) => p.split('*'))
    .filter((p) => /^[A-Z0-9]{10}$/.test(p[0]))
    .map((p) => ({ asin: p[0], qty: Math.max(1, Math.min(20, parseInt(p[1], 10) || 1)) }))
  const CART = '/cart/localmarket?almBrandId=' + BRAND
  const box = document.createElement('div')
  box.style.cssText = 'position:fixed;z-index:2147483647;top:12px;right:12px;width:320px;max-height:80vh;overflow:auto;background:#fff;border:3px solid #2d5a27;border-radius:12px;padding:14px;font:14px -apple-system,sans-serif;color:#333;box-shadow:0 8px 30px rgba(0,0,0,.25)'
  document.body.appendChild(box)
  const say = (html) => (box.innerHTML = '<b style="color:#2d5a27">Cookbook → Whole Foods</b><br>' + html)
  // Product titles come from Amazon's pages: escape them before they go into the status box.
  const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
  const frame = document.createElement('iframe')
  frame.style.cssText = 'position:fixed;left:-9999px;width:1024px;height:900px'
  document.body.appendChild(frame)
  const load = (url) =>
    new Promise((resolve) => {
      frame.onload = () => resolve()
      frame.src = url
    })
  // The Whole Foods cart page: one row per product, its quantity in data-quantity, a + button.
  const row = (doc, asin) => doc.querySelector('.sc-list-item[data-itemtype="active"][data-asin="' + asin + '"]')
  const qtyIn = (doc, asin) => {
    const r = row(doc, asin)
    return r ? parseInt(r.getAttribute('data-quantity'), 10) || 1 : 0
  }
  const SELECTORS = ['#freshAddToCartButton input', '#freshAddToCartButton button', '#freshAddToCartButton [type=submit]', 'input[name="submit.add-to-cart-ubb"]', '[data-action="fresh-add-to-cart"] input', '[data-action="fresh-add-to-cart"] button']
  const names = {}, added = [], already = [], failed = [], short = [], missing = new Set()
  ;(async () => {
    say('Checking your cart…')
    await load(CART)
    await sleep(1200)
    for (const it of items) it.before = qtyIn(frame.contentDocument, it.asin)
    for (let n = 0; n < items.length; n++) {
      const it = items[n]
      if (it.before > 0) {
        already.push(it.asin)
        continue
      }
      say(`Adding ${n + 1} of ${items.length}…<br><small>${it.asin}</small>`)
      try {
        await load('/dp/' + it.asin + '?fpw=alm&almBrandId=' + BRAND)
        await sleep(1500)
        const doc = frame.contentDocument
        const btn = SELECTORS.map((s) => doc.querySelector(s)).find(Boolean)
        names[it.asin] = esc(((doc.querySelector('#productTitle') || {}).textContent || it.asin).trim().slice(0, 60))
        if (!btn) {
          missing.add(it.asin)
          failed.push(names[it.asin] + ' (no Whole Foods add button: out of stock?)')
          continue
        }
        btn.click()
        await sleep(3000)
        added.push(it.asin)
      } catch (e) {
        missing.add(it.asin)
        failed.push(it.asin + ' (' + esc(e.message) + ')')
      }
    }
    const needMore = items.filter((it) => it.qty > 1 && !missing.has(it.asin))
    if (needMore.length) {
      say('Setting quantities…')
      await load(CART)
      await sleep(1500)
      for (const it of needMore) {
        for (let tries = 0; tries < 20 && qtyIn(frame.contentDocument, it.asin) < it.qty; tries++) {
          const r = row(frame.contentDocument, it.asin)
          const plus = r && r.querySelector('[data-action="qs-widget-increment-decl"] input, [data-action="qs-widget-increment-decl"] button')
          if (!plus) break
          plus.click()
          await sleep(2500)
        }
        const got = qtyIn(frame.contentDocument, it.asin)
        if (got < it.qty) short.push(`${names[it.asin] || it.asin}: ${got} of ${it.qty}`)
      }
    }
    frame.remove()
    const done = added.concat(already)
    say(
      `Added ${added.length}` + (already.length ? `, ${already.length} already in your cart` : '') + ` (${done.length} of ${items.length}).` +
        (short.length ? `<br><br><b>Check these quantities:</b><br>${short.join('<br>')}` : '') +
        (failed.length ? `<br><br><b>Not added:</b><br>${failed.join('<br>')}` : '') +
        `<br><br><button id="ckb-go" style="background:#2d5a27;color:#fff;border:0;border-radius:6px;padding:8px 12px">Show the cart</button>` +
        (done.length ? ` <button id="ckb-back" style="background:#fff;color:#2d5a27;border:1px solid #2d5a27;border-radius:6px;padding:7px 11px">Tick them off in Cookbook</button>` : ''),
    )
    box.querySelector('#ckb-go').onclick = () => {
      location.href = CART
    }
    const back = box.querySelector('#ckb-back')
    if (back) back.onclick = () => window.open(SITE + '/list?in_cart=' + done.join(','), '_blank')
  })()
}

/** The javascript: URL for the bookmark, with this cookbook's address baked in. */
export function bookmarkletHref(siteOrigin) {
  return 'javascript:(' + encodeURIComponent(loader.toString()) + ')(' + encodeURIComponent(JSON.stringify(siteOrigin)) + ')'
}

export { loader }
