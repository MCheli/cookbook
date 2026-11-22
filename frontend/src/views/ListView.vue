<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, errorMessage } from '@/api'
import { useList } from '@/stores/list'
import { useSession } from '@/stores/session'
import ProductPicker from '@/components/ProductPicker.vue'
import { FACTORS, price } from '@/lib/format'
import { printRecipes } from '@/lib/print'
import { toast } from '@/lib/toast'

const store = useList()
const session = useSession()
const picking = ref(null)
const newItem = ref({ name: '', amount_text: '' })
const suggestions = ref(null)
const matches = ref(null)
const aiBusy = ref('')
const showHave = ref(false)

const route = useRoute()
const router = useRouter()

onMounted(async () => {
  await store.load()
  // Back from the cart bookmark ("Tick them off in Cookbook"): ?in_cart=ASIN,ASIN
  const asins = new Set(String(route.query.in_cart || '').split(',').filter((a) => /^[A-Z0-9]{10}$/.test(a)))
  if (!asins.size || session.demo) return
  router.replace({ query: {} })
  const items = (store.list?.aisles ?? []).flatMap((a) => a.items).filter((i) => i.product && asins.has(i.product.asin) && !i.in_cart && !i.have)
  for (const i of items) await run(() => store.patchItem(i.id, { in_cart: true }))
  if (items.length) toast(`Ticked off ${items.length} item${items.length > 1 ? 's' : ''} in your cart.`)
})
const list = computed(() => store.list)
const allInCart = computed(() => !!list.value?.counts.need && list.value.counts.in_cart >= list.value.counts.need)
const visibleAisles = computed(() => (list.value?.aisles ?? []).filter((a) => showHave.value || a.items.some((i) => !i.have)))

async function run(fn, ok) {
  try {
    await fn()
    if (ok) toast(ok)
  } catch (e) {
    toast(errorMessage(e), 'error')
  }
}

async function print() {
  const full = await Promise.all(list.value.recipes.map((r) => api.get(`/recipes/${r.slug}`).then((x) => ({ ...x.data, factor: r.servings_factor }))))
  printRecipes(full)
}

function sendToCart() {
  if (!list.value.cart.items.length) {
    toast('Pick products for the items first.', 'error')
    return
  }
  window.open(list.value.cart.loader_url, '_blank', 'noopener')
}

// Add/Find open the product on Whole Foods in a new tab (or the Amazon app); the click itself
// ticks the item as in the cart, with undo, so the list shows what's left.
function addedToCart(item) {
  if (session.demo) return
  run(() => store.patchItem(item.id, { in_cart: true }))
}

async function pick(product) {
  const item = picking.value
  picking.value = null
  await run(() => store.patchItem(item.id, { product_id: product.id }))
}

async function addItem() {
  if (!newItem.value.name.trim()) return
  await run(() => store.addItem({ name: newItem.value.name, amount_text: newItem.value.amount_text || null }))
  newItem.value = { name: '', amount_text: '' }
}

async function suggest() {
  aiBusy.value = 'suggest'
  try {
    suggestions.value = (await api.post('/ai/suggest-week', { prompt: 'Plan this week.' })).data
  } catch (e) {
    toast(errorMessage(e), 'error')
  } finally {
    aiBusy.value = ''
  }
}

async function matchAi() {
  aiBusy.value = 'match'
  try {
    matches.value = (await api.post('/ai/match-products')).data.matches
    if (!matches.value.length) toast('No good matches in your products yet.')
  } catch (e) {
    toast(errorMessage(e), 'error')
  } finally {
    aiBusy.value = ''
  }
}

async function applyMatch(m) {
  await run(() => store.patchItem(m.item_id, { product_id: m.product.id }))
  matches.value = matches.value.filter((x) => x !== m)
}

async function done() {
  if (!confirm('Mark this list as ordered and start a new one?')) return
  await run(() => store.complete(), 'Saved to history. New list started.')
}
</script>

<template>
  <main class="mx-auto max-w-4xl px-4 py-6 sm:px-6">
    <div
      v-if="!list"
      class="py-12 text-center text-gray-500"
    >
      Loading…
    </div>
    <template v-else>
      <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 class="text-2xl font-semibold text-herb-600">
            This week
          </h2>
          <p class="text-sm text-gray-500">
            {{ list.title }}
          </p>
        </div>
        <div class="flex flex-wrap gap-2">
          <button
            class="btn-secondary btn-sm"
            :disabled="!list.recipes.length"
            @click="print"
          >
            Print recipes
          </button>
          <button
            v-demo-lock
            class="btn-secondary btn-sm"
            @click="run(() => store.addRegulars(), 'Added your regulars')"
          >
            Add my regulars
          </button>
          <button
            v-demo-lock
            class="btn-ghost btn-sm"
            :disabled="!list.recipes.length && !list.counts.total"
            @click="done"
          >
            Done shopping
          </button>
        </div>
      </div>

      <section class="card mb-5">
        <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 class="font-semibold">
            Recipes
          </h3>
          <div class="flex gap-2">
            <button
              v-if="session.hasAiKey"
              v-demo-lock
              class="btn-ghost btn-sm"
              :disabled="!!aiBusy"
              @click="suggest"
            >
              {{ aiBusy === 'suggest' ? 'Thinking…' : '✨ Suggest meals' }}
            </button>
            <RouterLink
              to="/"
              class="btn-ghost btn-sm"
            >
              + Add recipes
            </RouterLink>
          </div>
        </div>
        <p
          v-if="!list.recipes.length"
          class="text-sm text-gray-500"
        >
          Nothing yet. Pick recipes on the <RouterLink
            to="/"
            class="text-herb-600 underline"
          >
            recipes page
          </RouterLink>.
        </p>
        <ul class="divide-y">
          <li
            v-for="r in list.recipes"
            :key="r.recipe_id"
            class="flex items-center justify-between gap-3 py-2"
          >
            <RouterLink
              :to="`/r/${r.slug}`"
              class="min-w-0 truncate font-medium hover:underline"
            >
              {{ r.emoji }} {{ r.title }}
            </RouterLink>
            <div class="flex shrink-0 items-center gap-2">
              <select
                v-demo-lock
                class="input w-auto py-1 text-sm"
                :value="r.servings_factor"
                aria-label="Amount"
                @change="run(() => store.setFactor(r.recipe_id, +$event.target.value))"
              >
                <option
                  v-for="f in FACTORS"
                  :key="f"
                  :value="f"
                >
                  ×{{ f }}
                </option>
              </select>
              <button
                v-demo-lock
                class="text-sm text-gray-400 hover:text-red-700"
                aria-label="Remove"
                @click="run(() => store.removeRecipe(r.recipe_id))"
              >
                ✕
              </button>
            </div>
          </li>
        </ul>
        <div
          v-if="suggestions"
          class="mt-4 rounded-lg bg-violet-50 p-3"
        >
          <p class="mb-2 text-sm font-medium text-violet-900">
            Suggestions
          </p>
          <ul class="space-y-2">
            <li
              v-for="p in suggestions.picks"
              :key="p.slug"
              class="flex items-start justify-between gap-2 text-sm"
            >
              <span><RouterLink
                :to="`/r/${p.slug}`"
                class="font-medium underline"
              >{{ p.emoji }} {{ p.title }}</RouterLink> — {{ p.reason }}</span>
              <button
                v-if="!store.recipeIds.has(p.id)"
                class="btn-primary btn-sm shrink-0"
                @click="run(() => store.addRecipe(p.id))"
              >
                Add
              </button>
            </li>
            <li
              v-if="suggestions.new_idea"
              class="text-sm"
            >
              New idea: <strong>{{ suggestions.new_idea.emoji }} {{ suggestions.new_idea.title }}</strong> — {{ suggestions.new_idea.pitch }}
              <RouterLink
                :to="{ name: 'new', query: { idea: suggestions.new_idea.title + ': ' + suggestions.new_idea.pitch } }"
                class="ml-1 text-herb-600 underline"
              >
                Write it
              </RouterLink>
            </li>
          </ul>
        </div>
      </section>

      <section class="card mb-5 border-2 border-amazon-500/40">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="min-w-0 flex-1">
            <h3 class="font-semibold">
              Whole Foods
            </h3>
            <p
              v-if="!list.counts.need"
              class="text-sm text-gray-600"
            >
              Nothing to buy yet.
            </p>
            <p
              v-else-if="allInCart"
              class="text-sm font-medium text-herb-600"
            >
              Everything's in your cart. Check out on Amazon when you're ready.
            </p>
            <p
              v-else
              class="text-sm text-gray-600"
            >
              {{ list.counts.in_cart }} of {{ list.counts.need }} in your cart · tap <strong>Add</strong> on each item below
            </p>
            <div
              v-if="list.counts.need"
              class="mt-2 h-1.5 overflow-hidden rounded-full bg-gray-100"
            >
              <div
                class="h-full rounded-full bg-amazon-500 transition-all"
                :style="{ width: (100 * list.counts.in_cart) / list.counts.need + '%' }"
              />
            </div>
          </div>
          <div class="flex flex-wrap gap-2">
            <button
              v-if="session.hasAiKey && list.cart.unmatched.length"
              v-demo-lock
              class="btn-ghost btn-sm"
              :disabled="!!aiBusy"
              @click="matchAi"
            >
              {{ aiBusy === 'match' ? 'Matching…' : '✨ Match products' }}
            </button>
            <a
              :href="session.demo ? undefined : list.cart.cart_url"
              target="_blank"
              rel="noopener"
              :class="allInCart ? 'btn-amazon' : 'btn-secondary btn-sm'"
            >Open my cart</a>
          </div>
        </div>
        <p class="mt-2 text-xs text-gray-500">
          Add opens the product you bought before; Search looks it up on Whole Foods, for when that listing is gone. Either way, add it to your cart there and come back. Checkout stays with you.
          <template v-if="list.cart.items.length > 1">
            On a computer with the <RouterLink
              to="/settings#cart-button"
              class="underline"
            >Cookbook cart bookmark</RouterLink>, you can
            <button
              v-demo-lock
              class="underline"
              @click="sendToCart"
            >
              add all {{ list.cart.items.length }} at once
            </button>.
          </template>
        </p>
        <ul
          v-if="matches?.length"
          class="mt-3 space-y-2 rounded-lg bg-violet-50 p-3"
        >
          <li
            v-for="m in matches"
            :key="m.item_id"
            class="flex items-start justify-between gap-2 text-sm"
          >
            <span><strong>{{ m.item_name }}</strong> → {{ m.product.title }} <span class="text-gray-500">({{ m.confidence }}: {{ m.reason }})</span></span>
            <button
              class="btn-primary btn-sm shrink-0"
              @click="applyMatch(m)"
            >
              Use
            </button>
          </li>
        </ul>
      </section>

      <div class="mb-2 flex items-center justify-between">
        <h3 class="font-semibold">
          Shopping list
          <span class="text-sm font-normal text-gray-500">({{ list.counts.need }} to buy)</span>
        </h3>
        <label class="flex items-center gap-2 text-sm text-gray-600">
          <input
            v-model="showHave"
            type="checkbox"
          > Show items I have
        </label>
      </div>
      <section
        v-for="a in visibleAisles"
        :key="a.aisle"
        class="card mb-4"
      >
        <h4 class="mb-2 border-b-2 border-herb-100 pb-1.5 font-semibold text-herb-600">
          {{ a.aisle }}
        </h4>
        <template
          v-for="i in a.items"
          :key="i.id"
        >
          <div
            v-if="showHave || !i.have"
            class="flex flex-col gap-2 border-b border-[#f0f0f0] py-2.5 last:border-0 sm:flex-row sm:items-center"
          >
            <label class="flex min-w-0 flex-1 cursor-pointer items-start gap-3">
              <input
                v-demo-lock
                type="checkbox"
                class="mt-1 h-5 w-5 shrink-0 accent-herb-600"
                :checked="i.have"
                :title="i.have ? 'Need it after all' : 'I have this'"
                @change="run(() => store.patchItem(i.id, { have: $event.target.checked }))"
              >
              <span class="min-w-0">
                <span
                  class="font-medium"
                  :class="{ 'text-gray-400 line-through': i.have, 'text-gray-500': i.in_cart && !i.have }"
                >{{ i.name }}</span>
                <span class="block text-[0.85rem] text-[#666]">
                  {{ i.amount_text }}
                  <span
                    v-if="i.recipe_titles.length > 1"
                    class="text-gray-400"
                  > · {{ i.recipe_titles.join(', ') }}</span>
                </span>
                <span
                  v-if="i.product && !i.have"
                  class="mt-0.5 block text-xs text-gray-500"
                  :title="i.product.notes || undefined"
                >
                  {{ i.product.title }}<template v-if="i.product.size_text"> · {{ i.product.size_text }}</template>
                  <template v-if="i.product.price_cents"> · {{ price(i.product.price_cents) }}</template>
                </span>
              </span>
            </label>
            <div
              v-if="!i.have"
              class="flex shrink-0 flex-wrap items-center gap-2 pl-8 sm:pl-0"
            >
              <template v-if="i.in_cart">
                <span class="rounded-md bg-herb-100 px-2.5 py-1 text-sm font-medium text-herb-600">✓ In cart</span>
                <button
                  v-demo-lock
                  class="text-xs text-gray-400 hover:text-gray-700"
                  @click="run(() => store.patchItem(i.id, { in_cart: false }))"
                >
                  undo
                </button>
              </template>
              <template v-else-if="i.product">
                <select
                  v-demo-lock
                  class="input w-auto py-0.5 text-sm"
                  :value="i.quantity"
                  aria-label="How many"
                  @change="run(() => store.patchItem(i.id, { quantity: +$event.target.value }))"
                >
                  <option
                    v-for="n in 6"
                    :key="n"
                    :value="n"
                  >
                    {{ n }}
                  </option>
                </select>
                <button
                  v-demo-lock
                  class="text-xs text-gray-400 hover:text-gray-700"
                  @click="picking = i"
                >
                  change
                </button>
                <a
                  v-demo-lock
                  :href="session.demo ? undefined : i.product.search_url"
                  target="_blank"
                  rel="noopener"
                  class="btn btn-sm border border-amazon-500 bg-white text-amazon-600 hover:bg-amazon-500/10"
                  title="Searches Whole Foods for this product, for when its old listing is gone"
                  @click="addedToCart(i)"
                >Search</a>
                <a
                  v-demo-lock
                  :href="session.demo ? undefined : i.product.url"
                  target="_blank"
                  rel="noopener"
                  class="btn-amazon btn-sm min-w-[4.5rem] justify-center"
                  :title="'Opens it on Whole Foods; add it to your cart there'"
                  @click="addedToCart(i)"
                >Add<template v-if="i.quantity > 1"> ×{{ i.quantity }}</template></a>
              </template>
              <template v-else>
                <button
                  v-demo-lock
                  class="btn-ghost btn-sm"
                  @click="picking = i"
                >
                  Choose product
                </button>
                <a
                  v-demo-lock
                  :href="session.demo ? undefined : i.search_url"
                  target="_blank"
                  rel="noopener"
                  class="btn btn-sm min-w-[4.5rem] border border-amazon-500 bg-white text-amazon-600 hover:bg-amazon-500/10"
                  title="Searches Whole Foods for it; add one to your cart there"
                  @click="addedToCart(i)"
                >Find</a>
              </template>
              <button
                v-if="i.source !== 'recipe'"
                v-demo-lock
                class="text-sm text-gray-400 hover:text-red-700"
                aria-label="Remove"
                @click="run(() => store.deleteItem(i.id))"
              >
                ✕
              </button>
            </div>
          </div>
        </template>
      </section>

      <form
        class="card flex flex-wrap gap-2"
        @submit.prevent="addItem"
      >
        <input
          v-model="newItem.name"
          class="input flex-[2]"
          placeholder="Add an item (paper towels, bananas…)"
        >
        <input
          v-model="newItem.amount_text"
          class="input flex-1"
          placeholder="Amount (optional)"
        >
        <button
          v-demo-lock
          class="btn-primary"
        >
          Add
        </button>
      </form>
    </template>

    <ProductPicker
      v-if="picking"
      :item="picking"
      @pick="pick"
      @close="picking = null"
    />
  </main>
</template>
