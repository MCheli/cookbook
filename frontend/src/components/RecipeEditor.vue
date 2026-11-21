<script setup>
import { reactive, watch } from 'vue'
import { methods } from '@/api'
import { useSession } from '@/stores/session'

const props = defineProps({
  initial: { type: Object, required: true },
  saving: { type: Boolean, default: false },
  submitLabel: { type: String, default: 'Save recipe' },
})
const emit = defineEmits(['save', 'cancel'])
const session = useSession()

function toForm(r) {
  return {
    title: r.title || '',
    emoji: r.emoji || '',
    method: r.method || 'stovetop-oven',
    description: r.description || '',
    servings_text: r.servings_text || '',
    prep_text: r.prep_text || '',
    cook_text: r.cook_text || '',
    tags: (r.tags || []).join(', '),
    visibility: r.visibility || 'private',
    status: r.status || 'published',
    notes: r.notes || '',
    ingredients: (r.ingredients?.length ? r.ingredients : [{ group: '', item: '', amount: '' }]).map((i) => ({ group: i.group || '', item: i.item || '', amount: i.amount || '' })),
    steps: r.steps?.length ? [...r.steps] : [''],
    grocery: [...(r.grocery || [])],
  }
}
const form = reactive(toForm(props.initial))
watch(() => props.initial, (r) => Object.assign(form, toForm(r)))

function move(arr, i, d) {
  const j = i + d
  if (j < 0 || j >= arr.length) return
  ;[arr[i], arr[j]] = [arr[j], arr[i]]
}

function submit() {
  emit('save', {
    ...props.initial,
    ...form,
    emoji: form.emoji || null,
    description: form.description || null,
    servings_text: form.servings_text || null,
    prep_text: form.prep_text || null,
    cook_text: form.cook_text || null,
    notes: form.notes || null,
    tags: form.tags.split(',').map((t) => t.trim()).filter(Boolean),
    ingredients: form.ingredients.filter((i) => i.item.trim()).map((i) => ({ group: i.group || null, item: i.item, amount: i.amount || null })),
    steps: form.steps.filter((s) => s.trim()),
    grocery: form.grocery.filter((g) => g.trim()),
  })
}
</script>

<template>
  <form
    class="space-y-5"
    @submit.prevent="submit"
  >
    <div class="grid gap-3 sm:grid-cols-[5rem_1fr_12rem]">
      <div>
        <label class="label">Emoji</label>
        <input
          v-model="form.emoji"
          class="input text-center text-xl"
          maxlength="8"
        >
      </div>
      <div>
        <label class="label">Title</label>
        <input
          v-model="form.title"
          class="input"
          required
        >
      </div>
      <div>
        <label class="label">Method</label>
        <select
          v-model="form.method"
          class="input"
        >
          <option
            v-for="(label, key) in methods"
            :key="key"
            :value="key"
          >
            {{ label }}
          </option>
        </select>
      </div>
    </div>
    <div class="grid gap-3 sm:grid-cols-3">
      <div>
        <label class="label">Servings</label>
        <input
          v-model="form.servings_text"
          class="input"
          placeholder="4–6"
        >
      </div>
      <div>
        <label class="label">Prep</label>
        <input
          v-model="form.prep_text"
          class="input"
          placeholder="10 min"
        >
      </div>
      <div>
        <label class="label">Cook</label>
        <input
          v-model="form.cook_text"
          class="input"
          placeholder="20 min (stovetop)"
        >
      </div>
    </div>
    <div>
      <label class="label">Description (optional)</label>
      <textarea
        v-model="form.description"
        class="input"
        rows="2"
      />
    </div>

    <div>
      <label class="label">Ingredients</label>
      <div class="space-y-2">
        <div
          v-for="(i, n) in form.ingredients"
          :key="n"
          class="grid grid-cols-[1fr_auto] gap-2 sm:grid-cols-[9rem_1fr_8rem_auto]"
        >
          <input
            v-model="i.group"
            class="input col-span-2 sm:col-span-1"
            placeholder="Group"
            list="ingredient-groups"
          >
          <input
            v-model="i.item"
            class="input"
            placeholder="Item, e.g. Garlic, minced"
          >
          <input
            v-model="i.amount"
            class="input order-last col-span-2 sm:order-none sm:col-span-1"
            placeholder="Amount"
          >
          <span class="flex items-center gap-1 text-gray-400">
            <button
              type="button"
              aria-label="Move up"
              @click="move(form.ingredients, n, -1)"
            >↑</button>
            <button
              type="button"
              aria-label="Remove"
              class="hover:text-red-700"
              @click="form.ingredients.splice(n, 1)"
            >✕</button>
          </span>
        </div>
        <datalist id="ingredient-groups">
          <option
            v-for="g in ['Protein', 'Vegetables', 'Produce', 'Pasta', 'Rice', 'Sauce', 'Dairy', 'Seasoning', 'Pantry', 'Liquids', 'Finish']"
            :key="g"
            :value="g"
          />
        </datalist>
        <button
          type="button"
          class="btn-ghost btn-sm"
          @click="form.ingredients.push({ group: form.ingredients.at(-1)?.group || '', item: '', amount: '' })"
        >
          + Ingredient
        </button>
      </div>
    </div>

    <div>
      <label class="label">Method <span class="font-normal text-gray-500">— start each step with a bold label, like **Brown Sausage** – …</span></label>
      <div class="space-y-2">
        <div
          v-for="(s, n) in form.steps"
          :key="n"
          class="flex gap-2"
        >
          <span class="pt-2 text-sm text-gray-500">{{ n + 1 }}.</span>
          <textarea
            v-model="form.steps[n]"
            class="input"
            rows="2"
          />
          <span class="flex flex-col text-gray-400">
            <button
              type="button"
              aria-label="Move up"
              @click="move(form.steps, n, -1)"
            >↑</button>
            <button
              type="button"
              aria-label="Remove"
              class="hover:text-red-700"
              @click="form.steps.splice(n, 1)"
            >✕</button>
          </span>
        </div>
        <button
          type="button"
          class="btn-ghost btn-sm"
          @click="form.steps.push('')"
        >
          + Step
        </button>
      </div>
    </div>

    <div>
      <label class="label">Grocery list (optional) <span class="font-normal text-gray-500">— like **Protein**: 1 lb chicken thighs</span></label>
      <div class="space-y-2">
        <div
          v-for="(g, n) in form.grocery"
          :key="n"
          class="flex gap-2"
        >
          <input
            v-model="form.grocery[n]"
            class="input"
          >
          <button
            type="button"
            class="text-gray-400 hover:text-red-700"
            aria-label="Remove"
            @click="form.grocery.splice(n, 1)"
          >
            ✕
          </button>
        </div>
        <button
          type="button"
          class="btn-ghost btn-sm"
          @click="form.grocery.push('')"
        >
          + Line
        </button>
      </div>
    </div>

    <div class="grid gap-3 sm:grid-cols-2">
      <div>
        <label class="label">Tags</label>
        <input
          v-model="form.tags"
          class="input"
          placeholder="chicken, weeknight"
        >
      </div>
      <div>
        <label class="label">Notes</label>
        <textarea
          v-model="form.notes"
          class="input"
          rows="2"
        />
      </div>
    </div>

    <div class="flex flex-wrap items-center gap-4 rounded-lg bg-gray-50 p-3 text-sm">
      <label class="flex items-center gap-2">
        <input
          v-model="form.status"
          type="checkbox"
          true-value="draft"
          false-value="published"
          class="accent-herb-600"
        > Keep as a draft
      </label>
      <label
        v-if="session.isOwner"
        class="flex items-center gap-2"
      >
        <input
          v-model="form.visibility"
          type="checkbox"
          true-value="public"
          false-value="private"
          class="accent-herb-600"
        > Public (in the cookbook for everyone)
      </label>
      <span
        v-else
        class="text-gray-500"
      >Your recipes are private to you.</span>
    </div>

    <div class="flex gap-2">
      <button
        v-demo-lock
        class="btn-primary"
        :disabled="saving"
      >
        {{ saving ? 'Saving…' : submitLabel }}
      </button>
      <button
        type="button"
        class="btn-secondary"
        @click="emit('cancel')"
      >
        Cancel
      </button>
    </div>
  </form>
</template>
