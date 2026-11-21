/**
 * The Whole Foods cart button: a bookmarklet that runs on amazon.com, in the cook's own signed-in
 * session. Amazon has no API for the Whole Foods cart, so this does what a person would do: open
 * each product's Whole Foods page (in a hidden frame on amazon.com) and press its add button.
 *
 * - On the cart page opened by "Send to Whole Foods cart", it reads the ASINs from the URL
 *   fragment (#cookbook-cart=ASIN*qty,...), which never leaves the browser, and adds them.
 * - On a product page, it opens the cookbook's "save product" form for that ASIN instead.
 *
 * It only ever adds to the cart. Checkout stays with the cook.
 */

function loader(SITE) {
  const BRAND = 'VUZHIFdob2xlIEZvb2Rz'
  if (!/(^|\.)amazon\.com$/.test(location.hostname)) {
    alert('Open this on amazon.com (the Whole Foods cart page your cookbook sends you to).')
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
    alert('Use "Send to Whole Foods cart" on your cookbook list first; it opens this page with the items.')
    return
  }
  const items = decodeURIComponent(hash[1])
    .split(',')
    .map((p) => p.split('*'))
    .filter((p) => /^[A-Z0-9]{10}$/.test(p[0]))
    .map((p) => ({ asin: p[0], qty: Math.max(1, Math.min(20, parseInt(p[1], 10) || 1)) }))
  const box = document.createElement('div')
  box.style.cssText = 'position:fixed;z-index:2147483647;top:12px;right:12px;width:320px;max-height:80vh;overflow:auto;background:#fff;border:3px solid #2d5a27;border-radius:12px;padding:14px;font:14px -apple-system,sans-serif;color:#333;box-shadow:0 8px 30px rgba(0,0,0,.25)'
  document.body.appendChild(box)
  const say = (html) => (box.innerHTML = '<b style="color:#2d5a27">Cookbook → Whole Foods</b><br>' + html)
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
  const frame = document.createElement('iframe')
  frame.style.cssText = 'position:fixed;left:-9999px;width:1024px;height:900px'
  document.body.appendChild(frame)
  const load = (url) =>
    new Promise((resolve) => {
      frame.onload = () => resolve()
      frame.src = url
    })
  const SELECTORS = ['#freshAddToCartButton input', '#freshAddToCartButton button', '#freshAddToCartButton [type=submit]', 'input[name="submit.add-to-cart-ubb"]', '[data-action="fresh-add-to-cart"] input', '[data-action="fresh-add-to-cart"] button']
  const done = [], failed = [], adjust = []
  ;(async () => {
    for (let n = 0; n < items.length; n++) {
      const it = items[n]
      say(`Adding ${n + 1} of ${items.length}…<br><small>${it.asin}</small>`)
      try {
        await load('/dp/' + it.asin + '?fpw=alm&almBrandId=' + BRAND)
        await sleep(1500)
        const doc = frame.contentDocument
        const btn = SELECTORS.map((s) => doc.querySelector(s)).find(Boolean)
        const name = ((doc.querySelector('#productTitle') || {}).textContent || it.asin).trim().slice(0, 60)
        if (!btn) {
          failed.push(name + ' (no Whole Foods add button: out of stock or already in cart?)')
          continue
        }
        btn.click()
        await sleep(3000)
        done.push(name)
        if (it.qty > 1) adjust.push(`${name}: set to ${it.qty}`)
      } catch (e) {
        failed.push(it.asin + ' (' + e.message + ')')
      }
    }
    frame.remove()
    say(
      `Added ${done.length} of ${items.length}.` +
        (adjust.length ? `<br><br><b>Set quantities in the cart:</b><br>${adjust.join('<br>')}` : '') +
        (failed.length ? `<br><br><b>Not added:</b><br>${failed.join('<br>')}` : '') +
        `<br><br><button id="ckb-go" style="background:#2d5a27;color:#fff;border:0;border-radius:6px;padding:8px 12px">Open the cart</button>`,
    )
    box.querySelector('#ckb-go').onclick = () => {
      location.href = '/cart/localmarket?almBrandId=' + BRAND
    }
  })()
}

/** The javascript: URL for the bookmark, with this cookbook's address baked in. */
export function bookmarkletHref(siteOrigin) {
  return 'javascript:(' + encodeURIComponent(loader.toString()) + ')(' + encodeURIComponent(JSON.stringify(siteOrigin)) + ')'
}

export { loader }
