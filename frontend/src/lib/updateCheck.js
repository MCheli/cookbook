import { onBeforeUnmount, onMounted, ref } from 'vue'

/**
 * A Home Screen web app resumes where it left off instead of reloading, so a deploy can go
 * unseen for days. When the app comes back to the foreground, fetch index.html and compare its
 * hashed entry script with the one this page loaded; if a newer build is live, offer a refresh.
 * Never reloads on its own, so nothing in progress is lost.
 */
function entryScript(doc) {
  const el = doc.querySelector('script[type="module"][src*="/assets/"]')
  return el ? el.getAttribute('src') : null
}

export function useUpdateCheck() {
  const updateReady = ref(false)
  const loaded = entryScript(document)
  let last = 0

  async function check() {
    if (!loaded || document.visibilityState !== 'visible' || Date.now() - last < 60_000) return
    last = Date.now()
    try {
      const html = await (await fetch('/', { cache: 'no-store' })).text()
      const live = entryScript(new DOMParser().parseFromString(html, 'text/html'))
      if (live && live !== loaded) updateReady.value = true
    } catch {
      // offline or mid-deploy: try again next time
    }
  }
  onMounted(() => document.addEventListener('visibilitychange', check))
  onBeforeUnmount(() => document.removeEventListener('visibilitychange', check))
  return { updateReady, reload: () => window.location.reload() }
}
