import { reactive } from 'vue'

export const toasts = reactive([])
let next = 1

/** A short message at the bottom of the screen. kind: 'ok' | 'error'. */
export function toast(message, kind = 'ok', ms = 3500) {
  const id = next++
  toasts.push({ id, message, kind })
  setTimeout(() => {
    const i = toasts.findIndex((t) => t.id === id)
    if (i >= 0) toasts.splice(i, 1)
  }, ms)
}
