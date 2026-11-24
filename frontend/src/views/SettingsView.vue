<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, errorMessage } from '@/api'
import { useSession } from '@/stores/session'
import { bookmarkletHref } from '@/lib/cartLoader'
import { toast } from '@/lib/toast'

const session = useSession()
const router = useRouter()

const keyInput = ref('')
const keyBusy = ref(false)
const prefs = ref({ likes: '', dislikes: '', notes: '' })
const usage = ref(null)
const apiKeys = ref([])
const newKeyName = ref('')
const createdKey = ref(null)
const bookmarklet = computed(() => bookmarkletHref(window.location.origin))

onMounted(async () => {
  prefs.value = { likes: '', dislikes: '', notes: '', ...(session.user?.preferences || {}) }
  const [u, k] = await Promise.all([api.get('/me/usage'), api.get('/me/api-keys')])
  usage.value = u.data
  apiKeys.value = k.data
})

async function saveKey() {
  keyBusy.value = true
  try {
    session.setUser((await api.put('/me/anthropic-key', { key: keyInput.value.trim() })).data)
    keyInput.value = ''
    toast('Key saved. AI features are on.')
  } catch (e) {
    toast(errorMessage(e), 'error')
  } finally {
    keyBusy.value = false
  }
}
async function removeKey() {
  if (!confirm('Remove your Anthropic key? AI features turn off until you add one again.')) return
  session.setUser((await api.delete('/me/anthropic-key')).data)
}
async function savePrefs() {
  session.setUser((await api.put('/me/preferences', prefs.value)).data)
  toast('Saved')
}
async function createKey() {
  try {
    createdKey.value = (await api.post('/me/api-keys', { name: newKeyName.value || 'Agent' })).data
    newKeyName.value = ''
    apiKeys.value = (await api.get('/me/api-keys')).data
  } catch (e) {
    toast(errorMessage(e), 'error')
  }
}
async function revoke(k) {
  if (!confirm(`Revoke "${k.name}"?`)) return
  await api.delete(`/me/api-keys/${k.id}`)
  apiKeys.value = apiKeys.value.filter((x) => x.id !== k.id)
}
async function copy(text, what) {
  try {
    await navigator.clipboard.writeText(text)
    toast(`${what} copied`)
  } catch {
    toast("Couldn't copy; select and copy it by hand.", 'error')
  }
}
async function signOut() {
  await session.logout()
  router.push('/')
}
</script>

<template>
  <main class="mx-auto max-w-3xl space-y-6 px-4 py-6 sm:px-6">
    <h2 class="text-2xl font-semibold text-herb-600">
      Settings
    </h2>

    <section class="card space-y-3">
      <h3 class="font-semibold">
        Your Anthropic API key
      </h3>
      <p class="text-sm text-gray-600">
        The assistant (changing recipes, writing new ones, chat, photo import) runs on your own key, billed to your Anthropic account.
        It's stored encrypted and never shown again. Create one at
        <a
          href="https://console.anthropic.com/settings/keys"
          target="_blank"
          rel="noopener"
          class="text-herb-600 underline"
        >console.anthropic.com</a>; a workspace with a monthly spend limit caps what it can cost.
      </p>
      <div
        v-if="session.hasAiKey"
        class="flex flex-wrap items-center gap-3"
      >
        <span class="rounded-md bg-herb-50 px-3 py-1.5 font-mono text-sm">sk-ant-…{{ session.user.anthropic_key_last4 }}</span>
        <button
          v-demo-lock
          class="btn-ghost btn-sm text-red-700"
          @click="removeKey"
        >
          Remove
        </button>
      </div>
      <form
        class="flex gap-2"
        @submit.prevent="saveKey"
      >
        <input
          v-model="keyInput"
          type="password"
          autocomplete="off"
          class="input font-mono"
          :placeholder="session.hasAiKey ? 'Replace with a new key' : 'sk-ant-…'"
        >
        <button
          v-demo-lock
          class="btn-primary"
          :disabled="keyBusy || keyInput.trim().length < 20"
        >
          {{ keyBusy ? 'Checking…' : 'Save' }}
        </button>
      </form>
      <div
        v-if="usage"
        class="text-sm text-gray-600"
      >
        This month: about <strong>${{ usage.estimated_usd.toFixed(2) }}</strong>
        <span v-if="usage.models.length">({{ usage.models.map((m) => `${m.calls} calls on ${m.model}`).join(', ') }})</span>
        <span class="text-gray-400"> · an estimate; your Anthropic console has the real bill.</span>
      </div>
    </section>

    <form
      class="card space-y-3"
      @submit.prevent="savePrefs"
    >
      <h3 class="font-semibold">
        Food profile
      </h3>
      <p class="text-sm text-gray-600">
        The assistant keeps this in mind for every suggestion.
      </p>
      <div>
        <label class="label">Likes</label>
        <input
          v-model="prefs.likes"
          class="input"
          placeholder="Bold, simple, dump-and-go dinners"
        >
      </div>
      <div>
        <label class="label">Dislikes or avoid</label>
        <input
          v-model="prefs.dislikes"
          class="input"
          placeholder="Mango, mushrooms…"
        >
      </div>
      <div>
        <label class="label">Anything else</label>
        <textarea
          v-model="prefs.notes"
          class="input"
          rows="2"
          placeholder="Cooking for one; leftovers for lunch; Instant Pot and a crockpot"
        />
      </div>
      <button
        v-demo-lock
        class="btn-primary"
      >
        Save
      </button>
    </form>

    <section
      id="cart-button"
      class="card space-y-3"
    >
      <h3 class="font-semibold">
        Save products from Whole Foods (computer, optional)
      </h3>
      <p class="text-sm text-gray-600">
        A bookmark that, clicked on a Whole Foods product page on amazon.com, saves that product to your <RouterLink
          to="/products"
          class="underline"
        >Products</RouterLink>, so your orders link straight to it. Drag it to your bookmarks bar once →
        <a
          :href="bookmarklet"
          class="ml-1 inline-block rounded-md bg-amazon-500 px-3 py-1 font-medium text-white"
          @click.prevent="toast('Drag it to your bookmarks bar instead of clicking it.')"
        >Save to Cookbook</a>
      </p>
      <p class="text-xs text-gray-500">
        On a phone, use the <strong>Whole Foods ↗</strong> button on each item of your <RouterLink
          to="/list"
          class="underline"
        >order</RouterLink> instead.
      </p>
    </section>

    <section class="card space-y-3">
      <h3 class="font-semibold">
        API keys for agents
      </h3>
      <p class="text-sm text-gray-600">
        Let an agent (like a Claude session) read the current order's cart or record purchases, with the <code>X-API-Key</code> header.
      </p>
      <ul
        v-if="apiKeys.length"
        class="divide-y text-sm"
      >
        <li
          v-for="k in apiKeys"
          :key="k.id"
          class="flex items-center justify-between py-1.5"
        >
          <span>{{ k.name }} <span class="font-mono text-gray-500">{{ k.key_prefix }}…</span> <span class="text-gray-400">{{ k.last_used_at ? 'used ' + k.last_used_at.slice(0, 10) : 'never used' }}</span></span>
          <button
            v-demo-lock
            class="text-red-700"
            @click="revoke(k)"
          >
            Revoke
          </button>
        </li>
      </ul>
      <div
        v-if="createdKey"
        class="rounded-lg bg-amber-50 p-3 text-sm"
      >
        Copy it now; it won't be shown again:
        <code class="mt-1 block break-all font-mono">{{ createdKey.key }}</code>
        <button
          class="mt-1 text-herb-600 underline"
          @click="copy(createdKey.key, 'Key')"
        >
          Copy
        </button>
      </div>
      <form
        class="flex gap-2"
        @submit.prevent="createKey"
      >
        <input
          v-model="newKeyName"
          class="input"
          placeholder="Name, e.g. mac-mini-agent"
        >
        <button
          v-demo-lock
          class="btn-secondary"
        >
          Create key
        </button>
      </form>
    </section>

    <section class="card flex items-center justify-between">
      <span class="text-sm text-gray-600">Signed in as {{ session.user?.email }}</span>
      <button
        class="btn-secondary"
        @click="signOut"
      >
        Sign out
      </button>
    </section>
  </main>
</template>
