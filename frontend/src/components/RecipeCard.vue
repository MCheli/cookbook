<script setup>
defineProps({
  recipe: { type: Object, required: true },
  selected: { type: Boolean, default: false },
  selectable: { type: Boolean, default: true },
})
defineEmits(['toggle'])
</script>

<template>
  <div
    class="card relative flex cursor-pointer flex-col transition hover:-translate-y-0.5 hover:shadow-[0_4px_16px_rgba(0,0,0,0.15)]"
    :class="selected ? 'border-[3px] border-herb-600 bg-herb-50' : 'border-[3px] border-transparent'"
    role="button"
    :aria-pressed="selected"
    @click="selectable && $emit('toggle', recipe)"
  >
    <div
      v-if="selectable"
      class="absolute right-4 top-4 flex h-6 w-6 items-center justify-center rounded border-2 bg-white font-bold"
      :class="selected ? 'border-herb-600 bg-herb-600 text-white' : 'border-gray-300'"
    >
      <span v-if="selected">✓</span>
    </div>
    <div class="mb-2 flex flex-wrap items-center gap-1.5 pr-8">
      <span class="chip">{{ recipe.method_label }}</span>
      <span
        v-if="recipe.source === 'ai' || recipe.source === 'remix'"
        class="ai-badge"
      >{{ recipe.source === 'ai' ? 'AI' : 'Variant' }}</span>
      <span
        v-if="recipe.status === 'draft'"
        class="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800"
      >Draft</span>
      <span
        v-if="recipe.is_mine && recipe.visibility === 'private'"
        class="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
      >Private</span>
    </div>
    <h3 class="mb-1 pr-8 text-[1.1rem] font-semibold leading-snug">
      <span
        v-if="recipe.emoji"
        class="mr-1"
      >{{ recipe.emoji }}</span>{{ recipe.title }}
    </h3>
    <div class="text-[0.85rem] text-[#666]">
      <template v-if="recipe.servings_text">
        {{ recipe.servings_text }} servings
      </template>
      <template v-if="recipe.prep_text">
        | Prep: {{ recipe.prep_text }}
      </template>
      <template v-if="recipe.cook_text">
        | Cook: {{ recipe.cook_text }}
      </template>
    </div>
    <div class="mt-auto pt-4">
      <RouterLink
        :to="`/r/${recipe.slug}`"
        class="tap inline-flex items-center rounded-md bg-herb-600 px-4 py-2 text-[0.85rem] font-medium text-white hover:bg-herb-700"
        @click.stop
      >
        View Recipe
      </RouterLink>
    </div>
  </div>
</template>
