<script setup>
import { onMounted, ref, watch } from 'vue'
import { api, errorMessage } from '@/api'
import { price } from '@/lib/format'

const props = defineProps({ item: { type: Object, required: true } })
const emit = defineEmits(['pick', 'close'])

const q = ref(props.item.key.replace(/^(manual|product):/, ''))
const results = ref([])
const adding = ref(false)
const form = ref({ link: '', title: '', size_text: '' })
const error = ref('')

async function search() {
  results.value = (await api.get('/products', { params: { q: q.value || undefined } })).data
}
onMounted(search)
let t
watch(q, () => {
  clearTimeout(t)
  t = setTimeout(search, 250)
})

function asinFrom(text) {
  const m = String(text).match(/(?:\/dp\/|\/gp\/product\/|^)([A-Z0-9]{10})(?:[/?&#]|$)/)
  return m ? m[1] : null
}

async function addNew() {
  error.value = ''
  const asin = asinFrom(form.value.link.trim())
  if (!asin) {
    error.value = 'Paste an Amazon product link or a 10-character ASIN.'
    return
  }
  try {
    const { data } = await api.post('/products', {
      asin,
      title: form.value.title.trim() || props.item.name,
      size_text: form.value.size_text.trim() || null,
      match_keys: props.item.source === 'recipe' ? [props.item.key] : [],
    })
    emit('pick', data)
  } catch (e) {
    error.value = errorMessage(e)
  }
}
</script>

<template>
  <div
    class="fixed inset-0 z-40 flex items-end justify-center bg-black/40 sm:items-center"
    @click.self="emit('close')"
  >
    <div class="max-h-[85dvh] w-full max-w-lg overflow-y-auto rounded-t-2xl bg-white p-5 sm:rounded-2xl">
      <div class="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 class="font-semibold">
            Product for “{{ item.name }}”
          </h3>
          <p
            v-if="item.amount_text"
            class="text-sm text-gray-500"
          >
            Needs {{ item.amount_text }}
          </p>
        </div>
        <button
          class="text-2xl leading-none text-gray-400"
          aria-label="Close"
          @click="emit('close')"
        >
          ×
        </button>
      </div>
      <input
        v-model="q"
        class="input mb-3"
        placeholder="Search your products"
        type="search"
        enterkeyhint="search"
      >
      <ul class="mb-4 divide-y">
        <li
          v-for="p in results"
          :key="p.id"
          class="flex items-center justify-between gap-3 py-2"
        >
          <div class="min-w-0">
            <div class="truncate text-sm font-medium">
              {{ p.title }}
            </div>
            <div class="text-xs text-gray-500">
              {{ p.size_text }} {{ price(p.price_cents) }}
              <span v-if="p.purchase_count">· bought {{ p.purchase_count }}×</span>
            </div>
          </div>
          <button
            class="btn-primary btn-sm"
            @click="emit('pick', p)"
          >
            Use
          </button>
        </li>
        <li
          v-if="!results.length"
          class="py-3 text-sm text-gray-500"
        >
          Nothing in your products matches.
        </li>
      </ul>
      <button
        v-if="!adding"
        class="btn-ghost btn-sm"
        @click="adding = true"
      >
        + Add a Whole Foods product
      </button>
      <form
        v-else
        class="space-y-2 rounded-lg bg-gray-50 p-3"
        @submit.prevent="addNew"
      >
        <p class="text-xs text-gray-600">
          Find it with
          <a
            :href="item.search_url"
            target="_blank"
            rel="noopener"
            class="text-herb-600 underline"
          >Whole Foods search</a>, then paste the product's link here.
        </p>
        <input
          v-model="form.link"
          class="input"
          placeholder="https://www.amazon.com/…/dp/B0…  or ASIN"
          inputmode="url"
          autocapitalize="off"
          autocorrect="off"
          spellcheck="false"
        >
        <input
          v-model="form.title"
          class="input"
          :placeholder="`Name (default: ${item.name})`"
        >
        <input
          v-model="form.size_text"
          class="input"
          placeholder="Size, e.g. 1 lb (optional)"
        >
        <p
          v-if="error"
          class="text-sm text-red-700"
        >
          {{ error }}
        </p>
        <button class="btn-primary btn-sm">
          Save and use
        </button>
      </form>
    </div>
  </div>
</template>
