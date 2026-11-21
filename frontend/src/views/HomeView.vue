<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api, errorMessage, methods } from '@/api'
import { useSession } from '@/stores/session'
import { useList } from '@/stores/list'
import RecipeCard from '@/components/RecipeCard.vue'
import { toast } from '@/lib/toast'

const session = useSession()
const list = useList()
const router = useRouter()

const recipes = ref([])
const loading = ref(true)
const method = ref('all')
const tag = ref(null)
const scope = ref('all')
const q = ref('')
const selected = ref(new Set(JSON.parse(sessionStorage.getItem('cookbook-selected') || '[]')))
const busy = ref(false)

function shuffle(a) {
  const out = [...a]
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[out[i], out[j]] = [out[j], out[i]]
  }
  return out
}

async function load() {
  loading.value = true
  try {
    const params = { scope: scope.value }
    recipes.value = shuffle((await api.get('/recipes', { params })).data)
  } catch (e) {
    toast(errorMessage(e, "Couldn't load recipes."), 'error')
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(scope, load)
watch(selected, (s) => sessionStorage.setItem('cookbook-selected', JSON.stringify([...s])), { deep: true })

const tags = computed(() => {
  const counts = {}
  for (const r of recipes.value) for (const t of r.tags) counts[t] = (counts[t] || 0) + 1
  return Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 12).map(([t]) => t)
})
const methodsPresent = computed(() => Object.keys(methods).filter((m) => recipes.value.some((r) => r.method === m)))

const shown = computed(() => {
  const needle = q.value.trim().toLowerCase()
  return recipes.value.filter(
    (r) =>
      (method.value === 'all' || r.method === method.value) &&
      (!tag.value || r.tags.includes(tag.value)) &&
      (!needle ||
        r.title.toLowerCase().includes(needle) ||
        r.ingredient_names.some((i) => i.toLowerCase().includes(needle)) ||
        r.tags.some((t) => t.includes(needle))),
  )
})

function toggle(r) {
  const s = new Set(selected.value)
  s.has(r.slug) ? s.delete(r.slug) : s.add(r.slug)
  selected.value = s
}
function clear() {
  selected.value = new Set()
}

function groceryList() {
  router.push({ name: 'grocery', query: { r: [...selected.value].join(',') } })
}

async function addToWeek() {
  busy.value = true
  try {
    for (const slug of selected.value) {
      const r = recipes.value.find((x) => x.slug === slug)
      if (r && !list.recipeIds.has(r.id)) await list.addRecipe(r.id)
    }
    clear()
    router.push('/list')
  } catch (e) {
    toast(errorMessage(e), 'error')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div>
    <div class="bg-herb-600 pb-6 text-center text-white">
      <p class="opacity-90">
        Select recipes to generate your grocery list
      </p>
    </div>
    <main class="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h2 class="text-2xl font-semibold text-herb-600">
          Recipes
        </h2>
        <div class="flex w-full gap-2 sm:w-auto">
          <button
            class="btn-secondary flex-1 sm:flex-none"
            :disabled="!selected.size"
            @click="clear"
          >
            Clear Selection
          </button>
          <button
            v-if="session.signedIn"
            v-demo-lock
            class="btn-primary flex-1 sm:flex-none"
            :disabled="!selected.size || busy"
            @click="addToWeek"
          >
            Add to this week ({{ selected.size }})
          </button>
          <button
            class="flex-1 sm:flex-none"
            :class="session.signedIn ? 'btn-secondary' : 'btn-primary'"
            :disabled="!selected.size"
            @click="groceryList"
          >
            Generate Grocery List ({{ selected.size }})
          </button>
        </div>
      </div>

      <div class="mb-3 flex flex-wrap gap-2">
        <button
          class="filter-btn"
          :class="{ active: method === 'all' }"
          @click="method = 'all'"
        >
          All
        </button>
        <button
          v-for="m in methodsPresent"
          :key="m"
          class="filter-btn"
          :class="{ active: method === m }"
          @click="method = m"
        >
          {{ methods[m] }}
        </button>
        <div class="ml-auto flex w-full gap-2 sm:w-auto">
          <select
            v-if="session.signedIn"
            v-model="scope"
            class="input sm:w-36"
            aria-label="Which recipes"
          >
            <option value="all">
              All recipes
            </option>
            <option value="mine">
              My recipes
            </option>
            <option value="saved">
              Saved
            </option>
          </select>
          <input
            v-model="q"
            type="search"
            class="input sm:w-56"
            placeholder="Search recipes or ingredients"
          >
        </div>
      </div>
      <div
        v-if="tags.length"
        class="mb-5 flex flex-wrap gap-1.5"
      >
        <button
          v-for="t in tags"
          :key="t"
          class="rounded-full px-2.5 py-0.5 text-xs"
          :class="tag === t ? 'bg-herb-600 text-white' : 'bg-white text-gray-600 ring-1 ring-gray-200 hover:ring-herb-400'"
          @click="tag = tag === t ? null : t"
        >
          {{ t }}
        </button>
      </div>

      <p
        v-if="loading"
        class="py-12 text-center text-gray-500"
      >
        Loading recipes…
      </p>
      <p
        v-else-if="!shown.length"
        class="py-12 text-center text-gray-500"
      >
        No recipes match.
        <RouterLink
          v-if="session.signedIn"
          to="/new"
          class="text-herb-600 underline"
        >
          Add one
        </RouterLink>
      </p>
      <div
        v-else
        class="grid grid-cols-1 gap-6 sm:grid-cols-[repeat(auto-fill,minmax(280px,1fr))]"
      >
        <RecipeCard
          v-for="r in shown"
          :key="r.id"
          :recipe="r"
          :selected="selected.has(r.slug)"
          @toggle="toggle"
        />
      </div>
    </main>
  </div>
</template>
