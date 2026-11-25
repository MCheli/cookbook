import { onMounted, onUnmounted } from 'vue'

/**
 * Keeps the screen on while the component is shown (a recipe, while cooking). The browser drops
 * the lock when the page is hidden, so it's taken again on return. Does nothing where the Screen
 * Wake Lock API is missing or refused (low battery mode, older iOS).
 */
export function useWakeLock() {
  let lock = null
  let asking = false
  let active = false

  async function request() {
    if (!active || lock || asking || !navigator.wakeLock || document.visibilityState !== 'visible') return
    asking = true
    try {
      lock = await navigator.wakeLock.request('screen')
      lock.addEventListener('release', () => (lock = null))
      if (!active) release()
    } catch {
      lock = null
    } finally {
      asking = false
    }
  }
  function release() {
    lock?.release().catch(() => {})
    lock = null
  }
  const onVisible = () => request()

  onMounted(() => {
    active = true
    document.addEventListener('visibilitychange', onVisible)
    request()
  })
  onUnmounted(() => {
    active = false
    document.removeEventListener('visibilitychange', onVisible)
    release()
  })
}
