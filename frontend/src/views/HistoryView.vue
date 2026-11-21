<script setup>
import { onMounted, ref } from 'vue'
import { api } from '@/api'

const lists = ref([])
const cooked = ref([])
onMounted(async () => {
  const [a, b] = await Promise.all([api.get('/lists/history'), api.get('/cooklog')])
  lists.value = a.data
  cooked.value = b.data
})
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
        Past lists
      </h2>
      <p
        v-if="!lists.length"
        class="card text-sm text-gray-600"
      >
        Lists you finish with “Done shopping” show up here.
      </p>
      <ul
        v-else
        class="card divide-y"
      >
        <li
          v-for="l in lists"
          :key="l.id"
          class="py-2"
        >
          <div class="flex items-center justify-between">
            <span class="font-medium">{{ l.title }}</span>
            <span class="text-sm text-gray-500">{{ l.items }} items</span>
          </div>
          <div class="text-sm text-gray-600">
            {{ l.recipes.join(' · ') || 'No recipes' }}
          </div>
        </li>
      </ul>
    </section>
  </main>
</template>
