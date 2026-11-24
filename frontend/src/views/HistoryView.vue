<script setup>
import { onMounted, ref } from 'vue'
import { api } from '@/api'
import { shortDate } from '@/lib/format'
import { printRecipes } from '@/lib/print'

const lists = ref([])
const cooked = ref([])
// Each order's full recipes, loaded ahead of the tap: an iPhone only prints straight from it.
const printable = ref({})
onMounted(async () => {
  const [a, b] = await Promise.all([api.get('/lists/history'), api.get('/cooklog')])
  lists.value = a.data
  cooked.value = b.data
  for (const l of lists.value.filter((x) => x.recipe_list.length).slice(0, 10)) load(l)
})

async function load(l) {
  try {
    printable.value = { ...printable.value, [l.id]: (await api.get(`/lists/${l.id}/print`)).data }
  } catch {
    printable.value = { ...printable.value, [l.id]: [] }
  }
}
</script>

<template>
  <main class="mx-auto grid max-w-5xl gap-6 px-4 py-6 sm:px-6 md:grid-cols-2">
    <section>
      <h2 class="mb-3 text-xl font-semibold text-herb-600">
        Cooked
      </h2>
      <p
        v-if="!cooked.length"
        class="card text-sm text-gray-600"
      >
        Nothing logged yet. Press “I made this” on a recipe after you cook it.
      </p>
      <ul
        v-else
        class="card divide-y"
      >
        <li
          v-for="c in cooked"
          :key="c.id"
          class="py-2"
        >
          <div class="flex items-center justify-between gap-2">
            <RouterLink
              :to="`/r/${c.slug}`"
              class="font-medium hover:underline"
            >
              {{ c.emoji }} {{ c.title }}
            </RouterLink>
            <span class="shrink-0 text-sm text-gray-500">{{ c.cooked_on }}</span>
          </div>
          <div class="text-sm text-gray-600">
            <span
              v-if="c.rating"
              class="text-amber-500"
            >{{ '★'.repeat(c.rating) }}</span>
            <span v-if="c.notes"> {{ c.notes }}</span>
          </div>
        </li>
      </ul>
    </section>
    <section>
      <h2 class="mb-3 text-xl font-semibold text-herb-600">
        Past orders
      </h2>
      <p
        v-if="!lists.length"
        class="card text-sm text-gray-600"
      >
        Orders you mark placed (“I placed this order”) show up here, with their recipes ready to print.
      </p>
      <ul
        v-else
        class="card divide-y"
      >
        <li
          v-for="l in lists"
          :key="l.id"
          class="py-3"
          data-test="past-order"
        >
          <div class="flex items-center justify-between gap-2">
            <span class="font-medium">Placed {{ shortDate(l.ordered_at) }}</span>
            <span class="text-sm text-gray-500">{{ l.items }} items</span>
          </div>
          <div class="text-sm text-gray-600">
            <template v-if="l.recipe_list.length">
              <template
                v-for="(r, n) in l.recipe_list"
                :key="r.recipe_id"
              >
                <RouterLink
                  :to="`/r/${r.slug}`"
                  class="hover:underline"
                >
                  {{ r.emoji }} {{ r.title }}<template v-if="r.servings_factor !== 1">
                    (×{{ r.servings_factor }})
                  </template>
                </RouterLink><template v-if="n < l.recipe_list.length - 1">
                  ·
                </template>
              </template>
            </template>
            <template v-else>
              No recipes
            </template>
          </div>
          <div
            v-if="l.recipe_list.length"
            class="mt-2"
          >
            <button
              v-if="printable[l.id]"
              class="btn-secondary btn-sm"
              :disabled="!printable[l.id].length"
              @click="printRecipes(printable[l.id])"
            >
              Print recipes
            </button>
            <button
              v-else
              class="btn-ghost btn-sm"
              @click="load(l)"
            >
              Get recipes ready to print
            </button>
          </div>
        </li>
      </ul>
    </section>
  </main>
</template>
