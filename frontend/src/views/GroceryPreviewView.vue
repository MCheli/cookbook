<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, errorMessage } from '@/api'
import { useSession } from '@/stores/session'
import { printRecipes } from '@/lib/print'
import { toast } from '@/lib/toast'

// The original site's flow, for anyone: pick recipes, get one combined list with Whole Foods
// search links, print the cooking instructions.
const route = useRoute()
const session = useSession()
const data = ref(null)
const slugs = computed(() => String(route.query.r || '').split(',').filter(Boolean))

onMounted(async () => {
  if (!slugs.value.length) return
  try {
    data.value = (await api.post('/grocery/preview', { recipe_slugs: slugs.value })).data
  } catch (e) {
    toast(errorMessage(e), 'error')
  }
})

async function print() {
  const full = await Promise.all(slugs.value.map((s) => api.get(`/recipes/${s}`).then((r) => r.data)))
  printRecipes(full)
}
</script>

<template>
  <main class="mx-auto max-w-4xl px-4 py-6 sm:px-6">
    <div class="card sm:p-8">
      <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h2 class="text-2xl font-semibold text-herb-600">
          Grocery List
        </h2>
        <div class="flex w-full gap-2 sm:w-auto">
          <button
            class="btn-primary flex-1 sm:flex-none"
            :disabled="!data"
            @click="print"
          >
            Print Cooking Instructions
          </button>
          <RouterLink
            to="/"
            class="btn-secondary flex-1 sm:flex-none"
          >
            Back to Recipes
          </RouterLink>
        </div>
      </div>
      <p
        v-if="!slugs.length"
        class="text-gray-600"
      >
        No recipes selected. <RouterLink
          to="/"
          class="text-herb-600 underline"
        >
          Pick some
        </RouterLink>.
      </p>
      <template v-if="data">
        <div class="mb-6 rounded-lg bg-[#f9f9f9] p-4">
          <h3 class="mb-2 font-semibold">
            Selected Recipes:
          </h3>
          <ul class="list-disc pl-6">
            <li
              v-for="r in data.recipes"
              :key="r.slug"
            >
              <RouterLink
                :to="`/r/${r.slug}`"
                class="hover:underline"
              >
                {{ r.emoji }} {{ r.title }}
              </RouterLink>
            </li>
          </ul>
        </div>
        <div
          v-for="a in data.aisles"
          :key="a.aisle"
          class="mb-8"
        >
          <h3 class="mb-3 border-b-2 border-herb-100 pb-2 text-[1.1rem] font-semibold text-herb-600">
            {{ a.aisle }}
          </h3>
          <div
            v-for="i in a.items"
            :key="i.key"
            class="flex flex-col gap-2 border-b border-[#f0f0f0] py-3 last:border-0 sm:flex-row sm:items-center sm:justify-between"
          >
            <div class="flex-1">
              <div class="font-medium">
                {{ i.name }}
              </div>
              <div class="text-[0.85rem] text-[#666]">
                {{ i.amount_text }}
              </div>
            </div>
            <a
              :href="i.product?.url || i.search_url"
              target="_blank"
              rel="noopener"
              class="btn-amazon btn-sm w-full sm:w-auto"
            >{{ i.product ? 'Your usual' : 'Whole Foods' }}</a>
          </div>
        </div>
        <p
          v-if="!session.signedIn"
          class="mt-4 rounded-lg bg-herb-50 p-4 text-sm text-gray-700"
        >
          <RouterLink
            :to="{ name: 'login', query: { next: route.fullPath } }"
            class="font-medium text-herb-600 underline"
          >
            Sign in
          </RouterLink>
          to keep a weekly list, remember your usual Whole Foods products and fill your cart in one go.
        </p>
      </template>
    </div>
  </main>
</template>
