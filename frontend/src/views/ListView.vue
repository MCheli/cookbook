<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api, errorMessage } from '@/api'
import { useList } from '@/stores/list'
import { useSession } from '@/stores/session'
import ProductPicker from '@/components/ProductPicker.vue'
import { FACTORS, price, shortDate } from '@/lib/format'
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
const confirmingPlaced = ref(false)
const placing = ref(false)
// Items whose Whole Foods page was opened this visit: their "In cart" box is highlighted, so it's
// clear what to tick on the way back. Opening a page never ticks anything by itself.
const opened = ref(new Set())

// The full recipes, loaded ahead of time: an iPhone only prints straight from the tap.
const printable = ref(null)
const lastPrintable = ref(null)

onMounted(() => store.load())

const list = computed(() => store.list)
const empty = computed(() => !!list.value && !list.value.recipes.length && !list.value.counts.total)
const lastOrder = computed(() => list.value?.last_order ?? null)
const allInCart = computed(() => !!list.value?.counts.need && list.value.counts.in_cart >= list.value.counts.need)
const visibleAisles = computed(() => (list.value?.aisles ?? []).filter((a) => showHave.value || a.items.some((i) => !i.have)))
const pdfUrl = computed(() => {
  const rs = list.value?.recipes ?? []
  if (!rs.length) return null
  return `/api/recipes/pdf?slugs=${rs.map((r) => r.slug).join(',')}&factors=${rs.map((r) => r.servings_factor).join(',')}`
})

const printKey = computed(() => (list.value?.recipes ?? []).map((r) => `${r.slug}*${r.servings_factor}`).join(','))
watch(
  printKey,
  async (key) => {
    printable.value = null
    if (!key || session.demo) return
    try {
      const data = (await api.get('/lists/current/print')).data
      if (key === printKey.value) printable.value = data
    } catch {
      // The Print button stays disabled; the PDF link still works.
    }
  },
  { immediate: true },
)
watch(
  () => (empty.value ? lastOrder.value?.id : null),
  async (id) => {
    lastPrintable.value = null
    if (!id || session.demo) return
    try {
      lastPrintable.value = (await api.get(`/lists/${id}/print`)).data
    } catch {
      // Leave the button disabled.
    }
  },
  { immediate: true },
)

async function run(fn, ok) {
  try {
    await fn()
    if (ok) toast(ok)
  } catch (e) {
    toast(errorMessage(e), 'error')
  }
}

function print() {
  if (printable.value?.length) printRecipes(printable.value)
}
function printLast() {
  if (lastPrintable.value?.length) printRecipes(lastPrintable.value)
}

function openedPage(item) {
  opened.value = new Set(opened.value).add(item.id)
}

function setInCart(item, value) {
  run(() => store.patchItem(item.id, { in_cart: value }))
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
    suggestions.value = (await api.post('/ai/suggest-week', { prompt: 'Plan this order.' })).data
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

async function placed() {
  placing.value = true
  try {
    await store.complete()
    confirmingPlaced.value = false
    opened.value = new Set()
    window.scrollTo({ top: 0 })
    toast('Order saved to History. This is a new, empty order.')
  } catch (e) {
    toast(errorMessage(e), 'error')
  } finally {
    placing.value = false
  }
}

async function reopen() {
  await run(() => store.reopen(lastOrder.value.id), 'Reopened your last order.')
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
            Current order
          </h2>
          <p
            class="text-sm text-gray-500"
            data-test="order-started"
          >
            Started {{ shortDate(list.created_at) }}<template v-if="list.recipes.length">
              · {{ list.recipes.length }} recipe{{ list.recipes.length > 1 ? 's' : '' }}
            </template><template v-if="list.counts.need">
              · {{ list.counts.need }} to buy
            </template>
          </p>
        </div>
        <button
          v-if="!empty"
          v-demo-lock
          class="btn-secondary btn-sm"
          @click="run(() => store.addRegulars(), 'Added your regulars')"
        >
          Add my regulars
        </button>
      </div>

      <section
        v-if="empty"
        class="card mb-5"
        data-test="empty-order"
      >
        <p class="mb-3 text-gray-700">
          Nothing in this order yet. Pick a few recipes and their groceries land here.
        </p>
        <div class="flex flex-wrap gap-2">
          <RouterLink
            to="/"
            class="btn-primary"
          >
            Pick recipes
          </RouterLink>
          <button
            v-demo-lock
            class="btn-secondary"
            @click="run(() => store.addRegulars(), 'Added your regulars')"
          >
            Add my regulars
          </button>
        </div>
        <div
          v-if="lastOrder"
          class="mt-5 border-t pt-4"
          data-test="last-order"
        >
          <p class="text-sm font-medium text-gray-800">
            Last order, placed {{ shortDate(lastOrder.ordered_at) }}
          </p>
          <p class="mt-0.5 text-sm text-gray-600">
            <template v-if="lastOrder.recipes.length">
              <template
                v-for="(r, n) in lastOrder.recipes"
                :key="r.recipe_id"
              >
                <RouterLink
                  :to="`/r/${r.slug}`"
                  class="hover:underline"
                >
                  {{ r.emoji }} {{ r.title }}
                </RouterLink><template v-if="n < lastOrder.recipes.length - 1">
                  ·
                </template>
              </template>
            </template>
            <template v-else>
              {{ lastOrder.items }} items, no recipes
            </template>
          </p>
          <div class="mt-3 flex flex-wrap gap-2">
            <button
              v-if="lastOrder.recipes.length"
              class="btn-secondary btn-sm"
              data-test="print-last"
              :disabled="!lastPrintable?.length"
              @click="printLast"
            >
              Print its recipes
            </button>
            <button
              v-demo-lock
              class="btn-ghost btn-sm"
              data-test="reopen"
              @click="reopen"
            >
              Reopen it
            </button>
          </div>
          <p class="mt-2 text-xs text-gray-500">
            Reopen it if you marked it placed by mistake. Every past order is in <RouterLink
              to="/history"
              class="underline"
            >
              History
            </RouterLink>.
          </p>
        </div>
      </section>

      <template v-else>
        <section class="card mb-5">
          <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h3 class="font-semibold">
              Recipes
            </h3>
            <div class="flex flex-wrap gap-2">
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
            No recipes, just groceries. <RouterLink
              to="/"
              class="text-herb-600 underline"
            >
              Pick recipes
            </RouterLink>
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
              <div class="flex shrink-0 items-center gap-1">
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
                  class="h-9 w-9 rounded-md text-gray-400 hover:bg-gray-100 hover:text-red-700"
                  :aria-label="`Remove ${r.title}`"
                  @click="run(() => store.removeRecipe(r.recipe_id))"
                >
                  ✕
                </button>
              </div>
            </li>
          </ul>
          <div
            v-if="list.recipes.length"
            class="mt-3 flex flex-wrap items-center gap-2 border-t pt-3"
          >
            <button
              class="btn-secondary btn-sm"
              data-test="print"
              :disabled="!printable?.length"
              @click="print"
            >
              {{ printable ? 'Print recipes' : 'Getting recipes ready…' }}
            </button>
            <a
              v-if="pdfUrl"
              :href="pdfUrl"
              target="_blank"
              rel="noopener"
              class="btn-ghost btn-sm"
            >PDF</a>
          </div>
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
                Nothing to buy.
              </p>
              <p
                v-else-if="allInCart"
                class="text-sm font-medium text-herb-600"
              >
                Everything's in your cart. Check out on Amazon, then mark the order placed below.
              </p>
              <p
                v-else
                class="text-sm text-gray-600"
                data-test="cart-progress"
              >
                {{ list.counts.in_cart }} of {{ list.counts.need }} in your cart
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
              >Open my cart ↗</a>
            </div>
          </div>
          <p
            v-if="list.counts.need && !allInCart"
            class="mt-2 text-xs text-gray-500"
          >
            For each item, tap <strong>Whole Foods ↗</strong>, add it to your cart there, then come back and tick <strong>In cart</strong>. Checkout stays with you.
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

        <div class="mb-2 flex items-center justify-between gap-2">
          <h3 class="font-semibold">
            Shopping list
            <span class="text-sm font-normal text-gray-500">({{ list.counts.need }} to buy)</span>
          </h3>
          <label class="flex items-center gap-2 text-sm text-gray-600">
            <input
              v-model="showHave"
              type="checkbox"
              class="h-4 w-4 accent-herb-600"
            > Show items I have
          </label>
        </div>
        <section
          v-for="a in visibleAisles"
          :key="a.aisle"
          class="card mb-4"
        >
          <h4 class="mb-1 border-b-2 border-herb-100 pb-1.5 font-semibold text-herb-600">
            {{ a.aisle }}
          </h4>
          <template
            v-for="i in a.items"
            :key="i.id"
          >
            <div
              v-if="showHave || !i.have"
              class="border-b border-[#f0f0f0] py-3 last:border-0"
              :data-test="`item-${i.key}`"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
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
                </div>
                <button
                  v-if="i.source !== 'recipe'"
                  v-demo-lock
                  class="-mr-2 h-9 w-9 shrink-0 rounded-md text-gray-400 hover:bg-gray-100 hover:text-red-700"
                  :aria-label="`Remove ${i.name}`"
                  @click="run(() => store.deleteItem(i.id))"
                >
                  ✕
                </button>
              </div>

              <div
                v-if="i.have"
                class="mt-2 flex items-center gap-2 text-sm text-gray-500"
              >
                You have this.
                <button
                  v-demo-lock
                  class="btn-ghost btn-sm"
                  @click="run(() => store.patchItem(i.id, { have: false }))"
                >
                  Need it after all
                </button>
              </div>
              <div
                v-else
                class="mt-2 flex flex-wrap items-center gap-2"
              >
                <template v-if="i.in_cart">
                  <button
                    v-demo-lock
                    class="btn btn-sm min-h-[2.25rem] border border-herb-600 bg-herb-100 text-herb-700"
                    data-test="in-cart"
                    aria-pressed="true"
                    @click="setInCart(i, false)"
                  >
                    ✓ In cart
                  </button>
                </template>
                <template v-else>
                  <a
                    v-demo-lock
                    :href="session.demo ? undefined : (i.product ? i.product.url : i.search_url)"
                    target="_blank"
                    rel="noopener"
                    class="btn-amazon btn-sm min-h-[2.25rem]"
                    data-test="open-wf"
                    :title="i.product ? 'Opens this product on Whole Foods' : 'Searches Whole Foods for it'"
                    @click="openedPage(i)"
                  >{{ i.product ? 'Whole Foods' : 'Find on Whole Foods' }} ↗</a>
                  <button
                    v-demo-lock
                    class="btn btn-sm min-h-[2.25rem] border"
                    :class="opened.has(i.id) ? 'border-herb-600 bg-herb-600 text-white' : 'border-gray-300 bg-white text-gray-700'"
                    data-test="in-cart"
                    aria-pressed="false"
                    @click="setInCart(i, true)"
                  >
                    ☐ In cart
                  </button>
                  <select
                    v-if="i.product"
                    v-demo-lock
                    class="input min-h-[2.25rem] w-auto py-0.5 text-sm"
                    :value="i.quantity"
                    aria-label="How many"
                    @change="run(() => store.patchItem(i.id, { quantity: +$event.target.value }))"
                  >
                    <option
                      v-for="n in 6"
                      :key="n"
                      :value="n"
                    >
                      ×{{ n }}
                    </option>
                  </select>
                </template>
                <span class="ml-auto flex items-center gap-1">
                  <a
                    v-if="i.product && !i.in_cart"
                    :href="session.demo ? undefined : i.product.search_url"
                    target="_blank"
                    rel="noopener"
                    class="px-1.5 py-1 text-xs text-gray-500 underline"
                    title="Searches Whole Foods for this product, for when its old listing is gone"
                    @click="openedPage(i)"
                  >search</a>
                  <button
                    v-if="!i.in_cart"
                    v-demo-lock
                    class="px-1.5 py-1 text-xs text-gray-500 underline"
                    @click="picking = i"
                  >
                    {{ i.product ? 'change' : 'choose product' }}
                  </button>
                  <button
                    v-if="!i.in_cart"
                    v-demo-lock
                    class="px-1.5 py-1 text-xs text-gray-500 underline"
                    data-test="have-it"
                    @click="run(() => store.patchItem(i.id, { have: true }))"
                  >
                    have it
                  </button>
                </span>
              </div>
            </div>
          </template>
        </section>
      </template>

      <form
        class="card mb-5 flex flex-wrap gap-2"
        @submit.prevent="addItem"
      >
        <input
          v-model="newItem.name"
          class="input min-w-[10rem] flex-[2]"
          placeholder="Add an item (paper towels, bananas…)"
          aria-label="Item"
        >
        <input
          v-model="newItem.amount_text"
          class="input min-w-[6rem] flex-1"
          placeholder="Amount (optional)"
          aria-label="Amount"
        >
        <button
          v-demo-lock
          class="btn-primary"
        >
          Add
        </button>
      </form>

      <section
        v-if="!empty"
        class="card mb-5"
        :class="allInCart ? 'border-2 border-herb-600' : ''"
        data-test="place-order"
      >
        <h3 class="font-semibold">
          Placed the order?
        </h3>
        <template v-if="!confirmingPlaced">
          <p class="mt-1 text-sm text-gray-600">
            Once you've checked out on Amazon, mark it placed. The order moves to History, where its recipes stay printable, and a new, empty order starts.
          </p>
          <button
            v-demo-lock
            class="mt-3"
            :class="allInCart ? 'btn-primary' : 'btn-secondary'"
            data-test="placed"
            @click="confirmingPlaced = true"
          >
            I placed this order
          </button>
        </template>
        <template v-else>
          <p class="mt-1 text-sm text-gray-700">
            <template v-if="list.counts.need > list.counts.in_cart">
              {{ list.counts.need - list.counts.in_cart }} item{{ list.counts.need - list.counts.in_cart > 1 ? "s aren't" : " isn't" }} ticked as in your cart.
            </template>
            Move this order to History and start a new one?
          </p>
          <div class="mt-3 flex flex-wrap gap-2">
            <button
              v-demo-lock
              class="btn-primary"
              data-test="confirm-placed"
              :disabled="placing"
              @click="placed"
            >
              Yes, I placed it
            </button>
            <button
              class="btn-secondary"
              @click="confirmingPlaced = false"
            >
              Not yet
            </button>
          </div>
        </template>
      </section>
    </template>

    <ProductPicker
      v-if="picking"
      :item="picking"
      @pick="pick"
      @close="picking = null"
    />
  </main>
</template>
