/** Small helpers shared by views: inline markdown, amounts, prices. */

function escapeHtml(s) {
  return String(s ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}

/** '**Brown** – cook *gently*' → safe HTML with <strong>/<em>. Everything else is escaped. */
export function inlineMd(text) {
  return escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*(?!\s)(.+?)\*(?!\*)/g, '$1<em>$2</em>')
}

const FRACTIONS = { '½': 1 / 2, '⅓': 1 / 3, '⅔': 2 / 3, '¼': 1 / 4, '¾': 3 / 4, '⅛': 1 / 8, '⅜': 3 / 8, '⅝': 5 / 8, '⅞': 7 / 8, '⅕': 1 / 5, '⅙': 1 / 6 }
const PRETTY = [[1 / 2, '½'], [1 / 3, '⅓'], [2 / 3, '⅔'], [1 / 4, '¼'], [3 / 4, '¾'], [1 / 8, '⅛'], [3 / 8, '⅜'], [5 / 8, '⅝'], [7 / 8, '⅞']]
const NUM = '(?:\\d+\\s*[½⅓⅔¼¾⅕⅛⅜⅝⅞⅙]|\\d+\\s+\\d+/\\d+|\\d+/\\d+|\\d+(?:\\.\\d+)?|\\.\\d+|[½⅓⅔¼¾⅕⅛⅜⅝⅞⅙])'
const AMOUNT = new RegExp(`^\\s*(${NUM})(?:\\s*(?:–|-|‑|to|—)\\s*(${NUM}))?\\s*(.*)$`, 'i')

function toNumber(s) {
  s = s.trim()
  if (FRACTIONS[s] !== undefined) return FRACTIONS[s]
  let m = s.match(/^(\d+)\s*([½⅓⅔¼¾⅕⅛⅜⅝⅞⅙])$/)
  if (m) return +m[1] + FRACTIONS[m[2]]
  m = s.match(/^(\d+)\s+(\d+)\/(\d+)$/)
  if (m) return +m[1] + +m[2] / +m[3]
  if (s.includes('/')) {
    const [a, b] = s.split('/')
    return +a / +b
  }
  return +s
}

export function formatNumber(q) {
  if (q <= 0) return '0'
  const whole = Math.floor(q + 1e-9)
  const frac = q - whole
  if (frac < 0.02) return String(whole)
  const [f, glyph] = PRETTY.reduce((best, p) => (Math.abs(p[0] - frac) < Math.abs(best[0] - frac) ? p : best))
  if (Math.abs(f - frac) < 0.025) return whole ? `${whole}${glyph}` : glyph
  return String(Math.round(q * 100) / 100)
}

/** '1 lb' × 1.5 → '1½ lb'; amounts that don't start with a number come back unchanged. */
export function scaleAmount(text, factor) {
  if (!text || factor === 1) return text
  const m = String(text).replaceAll(' ', ' ').match(AMOUNT)
  if (!m) return text
  const lo = formatNumber(toNumber(m[1]) * factor)
  const hi = m[2] ? `–${formatNumber(toNumber(m[2]) * factor)}` : ''
  return `${lo}${hi} ${m[3]}`.trim()
}

export function price(cents) {
  return cents == null ? '' : `$${(cents / 100).toFixed(2)}`
}

export const FACTORS = [0.5, 1, 1.5, 2, 3]
