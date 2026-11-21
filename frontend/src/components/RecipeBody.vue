<script setup>
import { computed } from 'vue'
import { inlineMd, scaleAmount } from '@/lib/format'

const props = defineProps({
  recipe: { type: Object, required: true },
  factor: { type: Number, default: 1 },
  // When showing an AI version, the recipe it came from: changed lines are highlighted.
  original: { type: Object, default: null },
  showGrocery: { type: Boolean, default: true },
})

const originalIngredients = computed(() => new Map((props.original?.ingredients ?? []).map((i) => [i.item.toLowerCase(), i.amount])))
const originalSteps = computed(() => new Set(props.original?.steps ?? []))

function ingredientClass(i) {
  if (!props.original) return ''
  const key = i.item.toLowerCase()
  if (!originalIngredients.value.has(key)) return 'diff-added'
  return originalIngredients.value.get(key) !== i.amount ? 'diff-changed' : ''
}
function stepClass(s) {
  return props.original && !originalSteps.value.has(s) ? 'diff-changed' : ''
}
const removed = computed(() => {
  if (!props.original) return []
  const now = new Set(props.recipe.ingredients.map((i) => i.item.toLowerCase()))
  return props.original.ingredients.filter((i) => !now.has(i.item.toLowerCase()))
})
</script>

<template>
  <div class="recipe-body">
    <h3>Ingredients</h3>
    <div class="overflow-x-auto">
      <table class="ingredients-table">
        <thead>
          <tr>
            <th>Category</th>
            <th>Item</th>
            <th>Amount</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(i, n) in recipe.ingredients"
            :key="n"
            :class="ingredientClass(i)"
          >
            <td class="text-gray-600">
              {{ n === 0 || recipe.ingredients[n - 1].group !== i.group ? i.group : '' }}
            </td>
            <td v-html="inlineMd(i.item)" />
            <td class="whitespace-nowrap">
              {{ scaleAmount(i.amount, factor) }}
            </td>
          </tr>
          <tr
            v-for="i in removed"
            :key="'removed-' + i.item"
            class="text-gray-400 line-through"
          >
            <td>{{ i.group }}</td>
            <td>{{ i.item }}</td>
            <td>{{ i.amount }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <h3>Method</h3>
    <ol class="method-steps">
      <li
        v-for="(s, n) in recipe.steps"
        :key="n"
        :class="stepClass(s)"
        v-html="inlineMd(s)"
      />
    </ol>

    <template v-if="showGrocery && recipe.grocery?.length">
      <h3>Grocery List</h3>
      <ul class="list-disc pl-6">
        <li
          v-for="(g, n) in recipe.grocery"
          :key="n"
          v-html="inlineMd(g)"
        />
      </ul>
    </template>

    <template v-if="recipe.notes">
      <h3>Notes</h3>
      <p class="whitespace-pre-line text-gray-700">
        {{ recipe.notes }}
      </p>
    </template>
  </div>
</template>
