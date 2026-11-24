<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api, errorMessage } from '@/api'
import { useSession } from '@/stores/session'
import { useList } from '@/stores/list'
import RecipeBody from '@/components/RecipeBody.vue'
import AssistBox from '@/components/AssistBox.vue'
import { FACTORS } from '@/lib/format'
import { printRecipes } from '@/lib/print'
import { inHomeScreenApp, preparePdf } from '@/lib/pdfShare'
import { toast } from '@/lib/toast'

const props = defineProps({ slug: { type: String, required: true } })
const session = useSession()
const list = useList()
const router = useRouter()

const recipe = ref(null)
const notFound = ref(false)
const factor = ref(1)
const version = ref(null) // an AI-adapted version being looked at
const useVersion = ref(false)
const logForm = ref({ rating: 0, notes: '' })
const busy = ref(false)

async function load() {
  notFound.value = false
  version.value = null
  useVersion.value = false
  try {
    recipe.value = (await api.get(`/recipes/${props.slug}`)).data
    document.title = `${recipe.value.title} · Cookbook`
  } catch (e) {
    if (e.response?.status === 404) notFound.value = true
    else toast(errorMessage(e), 'error')
  }
}
watch(() => props.slug, load, { immediate: true })

const shown = computed(() => (useVersion.value && version.value ? { ...recipe.value, ...version.value.recipe } : recipe.value))
const onList = computed(() => recipe.value && list.recipeIds.has(recipe.value.id))

async function toggleList() {
  busy.value = true
  try {
    if (onList.value) await list.removeRecipe(recipe.value.id)
    else {
      await list.addRecipe(recipe.value.id, factor.value)
      toast(`Added to your order${factor.value !== 1 ? ` (×${factor.value})` : ''}`)
    }
  } catch (e) {
    toast(errorMessage(e), 'error')
  } finally {
    busy.value = false
  }
}

// In the iPhone Home Screen app Print shares this PDF (Print, Save to Files), so it's fetched ahead.
const homeScreen = inHomeScreenApp()
const pdfHref = computed(() =>
  recipe.value ? `/api/recipes/${recipe.value.slug}/pdf${factor.value !== 1 && !useVersion.value ? `?factor=${factor.value}` : ''}` : null,
)
watch(pdfHref, (url) => preparePdf(url), { immediate: true })

function print() {
  if (homeScreen && useVersion.value) {
    // The PDF is made from the saved recipe; this version only exists on this screen.
    toast('Save this version first to print it from the Home Screen app, or print it from Safari.', 'error', 6000)
    return
  }
  printRecipes([{ ...shown.value, factor: useVersion.value ? 1 : factor.value }], pdfHref.value)
}

async function toggleSave() {
  const method = recipe.value.is_saved ? 'delete' : 'put'
  await api[method](`/recipes/${recipe.value.id}/save`)
  recipe.value.is_saved = !recipe.value.is_saved
  toast(recipe.value.is_saved ? 'Saved to your recipes' : 'Removed from saved')
}

async function copy() {
  try {
    const { data } = await api.post(`/recipes/${recipe.value.id}/copy`)
    toast('Copied to your recipes')
    router.push(`/r/${data.slug}/edit`)
  } catch (e) {
    toast(errorMessage(e), 'error')
  }
}

async function remove() {
  if (!confirm(`Delete "${recipe.value.title}"?`)) return
  await api.delete(`/recipes/${recipe.value.id}`)
  toast('Deleted')
  router.push('/')
}

async function saveVersion() {
  busy.value = true
  try {
    const v = version.value
    const payload = {
      ...v.recipe,
      title: v.recipe.title === recipe.value.title ? `${recipe.value.title} (${v.variant_name})` : v.recipe.title,
      notes: [v.recipe.notes, `Changes: ${v.change_summary.join('; ')}.`].filter(Boolean).join('\n\n'),
      parent_id: recipe.value.id,
      source: 'remix',
      visibility: 'private',
      status: 'published',
      ai_meta: { ...v.ai_meta, created_at: new Date().toISOString() },
    }
    const { data } = await api.post('/recipes', payload)
    toast('Saved as your own version')
    router.push(`/r/${data.slug}`)
  } catch (e) {
    toast(errorMessage(e), 'error')
  } finally {
    busy.value = false
  }
}

async function logCooked() {
  try {
    await api.post('/cooklog', { recipe_id: recipe.value.id, rating: logForm.value.rating || null, notes: logForm.value.notes || null })
    logForm.value = { rating: 0, notes: '' }
    toast('Logged. Enjoy!')
    await load()
  } catch (e) {
    toast(errorMessage(e), 'error')
  }
}

async function publish(visibility) {
  try {
    const { data } = await api.get(`/recipes/${recipe.value.slug}`)
    const body = { ...data, visibility, status: 'published' }
    recipe.value = (await api.put(`/recipes/${recipe.value.id}`, body)).data
    toast(visibility === 'public' ? 'Published to the cookbook' : 'Made private')
  } catch (e) {
    toast(errorMessage(e), 'error')
  }
}
</script>

<template>
  <main class="mx-auto max-w-4xl px-4 py-6 sm:px-6">
    <RouterLink
      to="/"
      class="text-sm text-herb-600 hover:underline"
    >
      ← All recipes
    </RouterLink>

    <div
      v-if="notFound"
      class="card mt-4 text-center"
    >
      <p class="text-lg">
        That recipe isn't here.
      </p>
      <p
        v-if="!session.signedIn"
        class="mt-2 text-sm text-gray-600"
      >
        If it's one of yours, <RouterLink
          :to="{ name: 'login', query: { next: `/r/${slug}` } }"
          class="text-herb-600 underline"
        >
          sign in
        </RouterLink> to see it.
      </p>
    </div>

    <article
      v-else-if="recipe"
      class="card mt-3 sm:p-8"
    >
      <div class="mb-2 flex flex-wrap items-center gap-1.5">
        <span class="chip">{{ recipe.method_label }}</span>
        <span
          v-if="recipe.source === 'ai'"
          class="ai-badge"
          :title="recipe.ai_meta?.prompt ? `Prompt: ${recipe.ai_meta.prompt}` : ''"
        >✨ Made with AI</span>
        <span
          v-if="recipe.parent"
          class="ai-badge"
        >Version of
          <RouterLink
            :to="`/r/${recipe.parent.slug}`"
            class="underline"
          >{{ recipe.parent.title }}</RouterLink>
        </span>
        <span
          v-if="recipe.status === 'draft'"
          class="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800"
        >Draft</span>
        <span
          v-if="recipe.can_edit && recipe.visibility === 'private'"
          class="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
        >Only you can see this</span>
        <span
          v-for="t in recipe.tags"
          :key="t"
          class="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
        >{{ t }}</span>
      </div>
      <h1 class="text-2xl font-bold leading-tight sm:text-3xl">
        <span
          v-if="shown.emoji"
          class="mr-1"
        >{{ shown.emoji }}</span>{{ shown.title }}
      </h1>
      <div class="mt-1 text-[#666]">
        <strong>{{ recipe.method_label }}</strong>
        <template v-if="shown.servings_text">
          | {{ shown.servings_text }} servings
        </template>
        <template v-if="shown.prep_text">
          | Prep: {{ shown.prep_text }}
        </template>
        <template v-if="shown.cook_text">
          | Cook: {{ shown.cook_text }}
        </template>
      </div>
      <p
        v-if="shown.description"
        class="mt-3 text-gray-700"
      >
        {{ shown.description }}
      </p>

      <div class="mt-5 flex flex-wrap items-center gap-2 print:hidden">
        <label
          v-if="!useVersion"
          class="flex items-center gap-1.5 text-sm text-gray-700"
        >
          Amount
          <select
            v-model.number="factor"
            class="input w-auto py-1.5"
          >
            <option
              v-for="f in FACTORS"
              :key="f"
              :value="f"
            >×{{ f }}</option>
          </select>
        </label>
        <button
          v-if="session.signedIn"
          v-demo-lock
          class="btn-primary"
          :disabled="busy"
          @click="toggleList"
        >
          {{ onList ? '✓ In your order' : 'Add to order' }}
        </button>
        <button
          class="btn-secondary"
          @click="print"
        >
          {{ homeScreen ? 'Print or save' : 'Print' }}
        </button>
        <a
          v-if="!homeScreen"
          class="btn-secondary"
          :href="pdfHref"
          target="_blank"
        >PDF</a>
        <template v-if="session.signedIn && !recipe.can_edit">
          <button
            v-demo-lock
            class="btn-ghost"
            @click="toggleSave"
          >
            {{ recipe.is_saved ? '♥ Saved' : '♡ Save' }}
          </button>
          <button
            v-demo-lock
            class="btn-ghost"
            @click="copy"
          >
            Make my own copy
          </button>
        </template>
        <template v-if="recipe.can_edit">
          <RouterLink
            v-demo-lock
            :to="`/r/${recipe.slug}/edit`"
            class="btn-ghost"
          >
            Edit
          </RouterLink>
          <button
            v-if="recipe.can_publish && recipe.visibility === 'private'"
            v-demo-lock
            class="btn-ghost"
            @click="publish('public')"
          >
            Publish
          </button>
          <button
            v-if="recipe.can_publish && recipe.visibility === 'public'"
            v-demo-lock
            class="btn-ghost"
            @click="publish('private')"
          >
            Make private
          </button>
          <button
            v-demo-lock
            class="btn-ghost text-red-700 hover:bg-red-50"
            @click="remove"
          >
            Delete
          </button>
        </template>
      </div>

      <div
        v-if="session.signedIn"
        class="mt-6 print:hidden"
      >
        <AssistBox
          v-if="!version"
          :recipe="recipe"
          @result="(v) => { version = v; useVersion = true }"
        />
        <section
          v-else
          class="rounded-xl border border-violet-200 bg-violet-50/60 p-4"
        >
          <div class="flex flex-wrap items-center gap-2">
            <span class="ai-badge">✨ {{ version.variant_name }}</span>
            <span class="text-sm text-gray-700">{{ version.change_summary.join(' · ') }}</span>
          </div>
          <p class="mt-1 text-xs text-gray-500">
            Highlighted lines changed. Nothing is saved unless you keep it.
          </p>
          <div class="mt-3 flex flex-wrap gap-2">
            <button
              class="btn-secondary btn-sm"
              @click="useVersion = !useVersion"
            >
              {{ useVersion ? 'Show the original' : 'Show this version' }}
            </button>
            <button
              class="btn-secondary btn-sm"
              @click="print"
            >
              Print this version
            </button>
            <button
              v-demo-lock
              class="btn-primary btn-sm"
              :disabled="busy"
              @click="saveVersion"
            >
              Keep as my version
            </button>
            <button
              class="btn-ghost btn-sm"
              @click="version = null; useVersion = false"
            >
              Discard
            </button>
          </div>
        </section>
      </div>

      <RecipeBody
        :recipe="shown"
        :factor="useVersion ? 1 : factor"
        :original="useVersion ? recipe : null"
      />

      <section
        v-if="recipe.variants?.length"
        class="mt-6"
      >
        <h3 class="mb-2 font-semibold text-herb-600">
          Other versions
        </h3>
        <ul class="space-y-1">
          <li
            v-for="v in recipe.variants"
            :key="v.slug"
          >
            <RouterLink
              :to="`/r/${v.slug}`"
              class="text-herb-600 underline"
            >
              {{ v.title }}
            </RouterLink>
          </li>
        </ul>
      </section>

      <p
        v-if="recipe.source_url"
        class="mt-6 text-sm text-gray-500"
      >
        Imported from <a
          :href="recipe.source_url"
          class="underline"
          rel="noopener"
          target="_blank"
        >{{ recipe.source_url }}</a>
      </p>
      <p
        v-if="recipe.ai_meta"
        class="mt-2 text-xs text-gray-500"
      >
        Written by {{ recipe.ai_meta.model }}<template v-if="recipe.ai_meta.prompt">
          from "{{ recipe.ai_meta.prompt }}"
        </template>.
      </p>

      <section
        v-if="session.signedIn"
        class="mt-8 border-t pt-5 print:hidden"
      >
        <h3 class="mb-2 font-semibold text-herb-600">
          Cooked it?
        </h3>
        <form
          class="flex flex-wrap items-center gap-2"
          @submit.prevent="logCooked"
        >
          <span class="flex">
            <button
              v-for="n in 5"
              :key="n"
              type="button"
              class="px-0.5 text-xl"
              :class="n <= logForm.rating ? 'text-amber-500' : 'text-gray-300'"
              :aria-label="`${n} stars`"
              @click="logForm.rating = n"
            >★</button>
          </span>
          <input
            v-model="logForm.notes"
            class="input min-w-0 basis-full sm:basis-auto sm:flex-1"
            placeholder="Notes for next time (optional)"
          >
          <button
            v-demo-lock
            class="btn-secondary"
          >
            I made this
          </button>
        </form>
        <ul
          v-if="recipe.cook_log?.length"
          class="mt-3 space-y-1 text-sm text-gray-600"
        >
          <li
            v-for="c in recipe.cook_log"
            :key="c.id"
          >
            {{ c.cooked_on }} <span
              v-if="c.rating"
              class="text-amber-500"
            >{{ '★'.repeat(c.rating) }}</span>
            <span v-if="c.notes"> · {{ c.notes }}</span>
          </li>
        </ul>
      </section>

      <p class="mt-6 text-xs text-gray-400 print:hidden">
        Export: <a
          :href="`/api/recipes/${recipe.slug}/markdown`"
          class="underline"
          target="_blank"
        >Markdown</a> ·
        <a
          :href="`/api/recipes/${recipe.slug}/jsonld`"
          class="underline"
          target="_blank"
        >schema.org JSON</a>
      </p>
    </article>
  </main>
</template>
