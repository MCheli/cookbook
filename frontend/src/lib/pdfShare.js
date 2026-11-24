import { toast } from './toast'

/**
 * Printing from the iPhone Home Screen app. There, window.print() does nothing and a PDF opens in
 * a bare viewer with no way to print or keep it. What does work is the share sheet, which offers
 * Print and Save to Files. Sharing a file only works straight from the tap, so each PDF is fetched
 * ahead of time (preparePdf, when the recipes it holds are known) and shared from the tap
 * (sharePdf). In Safari and everywhere else none of this runs: print and the PDF link work there.
 */

/** True only in an iPhone or iPad Home Screen web app (navigator.standalone is Apple's alone). */
export function inHomeScreenApp() {
  return typeof navigator !== 'undefined' && navigator.standalone === true
}

/** The PDF of these recipes, each at its own scale: [{ slug, factor }]. */
export function pdfUrlFor(recipes) {
  const rs = (recipes || []).filter((r) => r?.slug)
  if (!rs.length) return null
  const factors = rs.map((r) => r.factor ?? r.servings_factor ?? 1)
  const scaled = factors.some((f) => f !== 1)
  return `/api/recipes/pdf?slugs=${rs.map((r) => r.slug).join(',')}${scaled ? `&factors=${factors.join(',')}` : ''}`
}

const files = new Map() // url -> { file: File | null, failed: boolean }

/** Fetch this PDF now, so a later tap can share it. Does nothing outside the Home Screen app. */
export function preparePdf(url) {
  if (!url || !inHomeScreenApp()) return
  const seen = files.get(url)
  if (seen && !seen.failed) return
  const entry = { file: null, failed: false }
  files.set(url, entry)
  fetch(url, { credentials: 'same-origin' })
    .then((r) => (r.ok ? r.blob() : Promise.reject(new Error(String(r.status)))))
    .then((blob) => {
      entry.file = new File([blob], 'recipes.pdf', { type: 'application/pdf' })
    })
    .catch(() => {
      entry.failed = true
    })
}

/**
 * From the tap: open the share sheet with this PDF (Print, Save to Files, AirDrop). Returns false
 * outside the Home Screen app, so the caller prints or follows the link as usual.
 */
export function sharePdf(url) {
  if (!url || !inHomeScreenApp()) return false
  const entry = files.get(url)
  if (!entry || !entry.file) {
    if (!entry || entry.failed) preparePdf(url)
    toast(entry?.failed ? "Couldn't get the PDF. Try again in a moment." : 'Getting the PDF ready. Tap again in a moment.')
    return true
  }
  const data = { files: [entry.file], title: 'Recipes' }
  if (!navigator.canShare?.(data)) {
    // No file sharing here: Safari itself can print, so send the page there.
    toast(`Printing works from Safari: open ${location.host} there and tap Print.`, 'error', 6000)
    return true
  }
  navigator.share(data).catch(() => {}) // closing the sheet rejects; nothing to do
  return true
}

