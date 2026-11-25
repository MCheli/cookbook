<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, errorMessage } from '@/api'
import { useSession } from '@/stores/session'
import { price } from '@/lib/format'
import { toast } from '@/lib/toast'

const route = useRoute()
const router = useRouter()
const session = useSession()
const products = ref([])
const q = ref('')
const onlyRegulars = ref(false)
const editing = ref(null)
const adding = ref(null)

async function load() {
  products.value = (await api.get('/products', { params: { q: q.value || undefined, regulars: onlyRegulars.value || undefined } })).data
}
onMounted(() => {
  load()
  // Opened by the cart button on an Amazon product page: prefill the new product.
  if (route.query.add && route.query.asin) {
    const cents = Math.round(parseFloat(String(route.query.price || '').replace(/[^0-9.]/g, '')) * 100)
    adding.value = { asin: route.query.asin, title: route.query.title || '', size_text: '', price_cents: Number.isFinite(cents) ? cents : null, match_keys: '', is_regular: false, regular_qty: 1, notes: '' }
    router.replace({ query: {} })
  }
})
let t
watch([q, onlyRegulars], () => {
  clearTimeout(t)
  t = setTimeout(load, 250)
})

function startEdit(p) {
  editing.value = { ...p, match_keys: p.match_keys.join(', ') }
}
function startAdd() {
  adding.value = { asin: '', title: '', size_text: '', price_cents: null, match_keys: '', is_regular: false, regular_qty: 1, notes: '' }
}
function keys(s) {
  return String(s || '').split(',').map((k) => k.trim()).filter(Boolean)
}

async function saveEdit() {
  const p = editing.value
  try {
    await api.patch(`/products/${p.id}`, {
      title: p.title, size_text: p.size_text || null, notes: p.notes || null, match_keys: keys(p.match_keys),
      is_regular: p.is_regular, regular_qty: p.regular_qty, sold_by_weight: p.sold_by_weight,
    })
    editing.value = null
    await load()
  } catch (e) {
    toast(errorMessage(e), 'error')
  }
}

async function saveNew() {
  const p = adding.value
  const asin = (String(p.asin).match(/([A-Z0-9]{10})/) || [])[1]
  if (!asin) return toast('Paste the product link or its 10-character ASIN.', 'error')
  try {
    await api.post('/products', { ...p, asin, match_keys: keys(p.match_keys), notes: p.notes || null, size_text: p.size_text || null })
    adding.value = null
    toast('Product saved')
    await load()
  } catch (e) {
    toast(errorMessage(e), 'error')
  }
}

async function remove(p) {
  if (!confirm(`Remove "${p.title}" from your products?`)) return
  await api.delete(`/products/${p.id}`)
  await load()
}
</script>

<template>
  <main class="mx-auto max-w-4xl px-4 py-6 sm:px-6">
    <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 class="text-2xl font-semibold text-herb-600">
          Your Whole Foods products
        </h2>
        <p class="text-sm text-gray-600">
          What you usually buy for each ingredient. Orders match these automatically; regulars are the extras you add to most orders.
        </p>
      </div>
      <button
        v-demo-lock
        class="btn-primary"
        @click="startAdd"
      >
        + Add product
      </button>
    </div>
    <div class="mb-4 flex gap-2">
      <input
        v-model="q"
        type="search"
        class="input"
        placeholder="Search products or ingredients"
        enterkeyhint="search"
      >
      <label class="tap flex shrink-0 items-center gap-2 text-sm text-gray-700">
        <input
          v-model="onlyRegulars"
          type="checkbox"
          class="accent-herb-600"
        > Regulars only
      </label>
    </div>

    <form
      v-if="adding"
      class="card mb-4 space-y-3"
      @submit.prevent="saveNew"
    >
      <h3 class="font-semibold">
        New product
      </h3>
      <input
        v-model="adding.asin"
        class="input"
        placeholder="Amazon product link or ASIN"
        inputmode="url"
        autocapitalize="off"
        autocorrect="off"
        spellcheck="false"
      >
      <input
        v-model="adding.title"
        class="input"
        placeholder="Name"
      >
      <div class="flex gap-2">
        <input
          v-model="adding.size_text"
          class="input"
          placeholder="Size (1 lb, 16 oz…)"
        >
        <input
          v-model="adding.match_keys"
          class="input"
          placeholder="Ingredients it's for (comma separated)"
        >
      </div>
      <label class="tap flex items-center gap-2 text-sm">
        <input
          v-model="adding.is_regular"
          type="checkbox"
          class="accent-herb-600"
        > A regular
      </label>
      <div class="flex gap-2">
        <button
          v-demo-lock
          class="btn-primary"
        >
          Save
        </button>
        <button
          type="button"
          class="btn-secondary"
          @click="adding = null"
        >
          Cancel
        </button>
      </div>
    </form>

    <p
      v-if="!products.length"
      class="card text-gray-600"
    >
      No products yet. Choose a product for an item on your list, add one here, or tap your cart button on any Whole Foods product page.
    </p>
    <ul class="space-y-3">
      <li
        v-for="p in products"
        :key="p.id"
        class="card"
      >
        <form
          v-if="editing?.id === p.id"
          class="space-y-2"
          @submit.prevent="saveEdit"
        >
          <input
            v-model="editing.title"
            class="input"
          >
          <div class="flex gap-2">
            <input
              v-model="editing.size_text"
              class="input"
              placeholder="Size"
            >
            <label class="flex shrink-0 items-center gap-1.5 text-sm"><input
              v-model="editing.sold_by_weight"
              type="checkbox"
              class="accent-herb-600"
            > Sold by weight</label>
          </div>
          <input
            v-model="editing.match_keys"
            class="input"
            placeholder="Ingredients it's for (comma separated)"
          >
          <textarea
            v-model="editing.notes"
            class="input"
            rows="2"
            placeholder="Notes (e.g. packs run heavy; one covers 1½ lb)"
          />
          <div class="flex flex-wrap items-center gap-3">
            <label class="flex items-center gap-1.5 text-sm"><input
              v-model="editing.is_regular"
              type="checkbox"
              class="accent-herb-600"
            > Regular</label>
            <label
              v-if="editing.is_regular"
              class="flex items-center gap-1.5 text-sm"
            >Qty <input
              v-model.number="editing.regular_qty"
              type="number"
              min="1"
              max="50"
              inputmode="numeric"
              class="input w-16 py-1"
            ></label>
            <button
              v-demo-lock
              class="btn-primary btn-sm ml-auto"
            >
              Save
            </button>
            <button
              type="button"
              class="btn-secondary btn-sm"
              @click="editing = null"
            >
              Cancel
            </button>
          </div>
        </form>
        <div
          v-else
          class="flex items-start justify-between gap-3"
        >
          <div class="min-w-0">
            <a
              :href="session.demo ? undefined : p.url"
              target="_blank"
              rel="noopener"
              class="font-medium hover:underline"
            >{{ p.title }}</a>
            <div class="text-sm text-gray-500">
              {{ p.size_text }} {{ price(p.price_cents) }}
              <span v-if="p.purchase_count">· bought {{ p.purchase_count }}×, last {{ p.last_purchased_on }}</span>
              <span
                v-if="p.is_regular"
                class="ml-1 rounded-full bg-herb-100 px-2 text-xs text-herb-700"
              >regular ×{{ p.regular_qty }}</span>
            </div>
            <div
              v-if="p.match_keys.length"
              class="mt-1 flex flex-wrap gap-1"
            >
              <span
                v-for="k in p.match_keys"
                :key="k"
                class="rounded bg-gray-100 px-1.5 text-xs text-gray-600"
              >{{ k }}</span>
            </div>
            <p
              v-if="p.notes"
              class="mt-1 text-xs text-gray-500"
            >
              {{ p.notes }}
            </p>
          </div>
          <div class="flex shrink-0 gap-1">
            <button
              v-demo-lock
              class="btn-ghost btn-sm"
              @click="startEdit(p)"
            >
              Edit
            </button>
            <button
              v-demo-lock
              class="btn-ghost btn-sm min-w-11 text-red-700"
              @click="remove(p)"
            >
              ✕
            </button>
          </div>
        </div>
      </li>
    </ul>
  </main>
</template>
