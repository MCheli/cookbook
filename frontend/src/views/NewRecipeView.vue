<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, errorMessage } from '@/api'
import { useSession } from '@/stores/session'
import RecipeEditor from '@/components/RecipeEditor.vue'
import MicButton from '@/components/MicButton.vue'
import { toast } from '@/lib/toast'

const session = useSession()
const route = useRoute()
const router = useRouter()

const tab = ref('describe')
const prompt = ref('')
const url = ref('')
const markdown = ref('')
const ideas = ref(null)
const draft = ref(null)
const via = ref('')
const busy = ref('')
const saving = ref(false)

onMounted(() => {
  if (route.query.idea) {
    prompt.value = String(route.query.idea)
  }
  if (!session.hasAiKey) tab.value = 'link'
})

async function call(kind, fn) {
  busy.value = kind
  try {
    await fn()
  } catch (e) {
    toast(errorMessage(e), 'error')
  } finally {
    busy.value = ''
  }
}

const brainstorm = () => call('ideas', async () => {
  ideas.value = (await api.post('/ai/ideas', { prompt: prompt.value })).data.ideas
})

const write = (text) => call('generate', async () => {
  const { data } = await api.post('/ai/generate', { prompt: text || prompt.value })
  draft.value = { ...data.recipe, source: 'ai', ai_meta: { ...data.ai_meta, created_at: new Date().toISOString() }, status: 'published', visibility: 'private' }
  via.value = 'ai'
})

const fromLink = () => call('link', async () => {
  const { data } = await api.post('/ai/import-url', { url: url.value })
  draft.value = { ...data.recipe, source_url: url.value, source: 'import', status: 'published', visibility: 'private' }
  via.value = data.via
})

async function fromPhoto(e) {
  const file = e.target.files?.[0]
  if (!file) return
  await call('photo', async () => {
    const body = new FormData()
    body.append('file', file)
    const { data } = await api.post('/ai/import-photo', body, { headers: { 'Content-Type': 'multipart/form-data' } })
    draft.value = { ...data.recipe, source: 'import', status: 'published', visibility: 'private' }
    via.value = 'photo'
  })
}

const fromMarkdown = () => call('md', async () => {
  const { data } = await api.post('/recipes/import/markdown', { markdown: markdown.value })
  toast('Recipe added')
  router.push(`/r/${data.slug}/edit`)
})

function blank() {
  draft.value = { title: '', method: 'stovetop-oven', ingredients: [], steps: [], grocery: [], status: 'published', visibility: 'private', source: 'manual' }
  via.value = ''
}

async function save(payload) {
  saving.value = true
  try {
    const { data } = await api.post('/recipes', payload)
    toast('Recipe saved')
    router.push(`/r/${data.slug}`)
  } catch (e) {
    toast(errorMessage(e), 'error')
  } finally {
    saving.value = false
  }
}

const TABS = [
  ['describe', '✨ Describe it'],
  ['link', 'From a link'],
  ['photo', '✨ From a photo'],
  ['markdown', 'Paste markdown'],
  ['blank', 'Write it yourself'],
]
</script>

<template>
  <main class="mx-auto max-w-4xl px-4 py-6 sm:px-6">
    <h2 class="mb-4 text-2xl font-semibold text-herb-600">
      New recipe
    </h2>

    <template v-if="!draft">
      <div class="mb-4 flex flex-wrap gap-2">
        <button
          v-for="[key, label] in TABS"
          :key="key"
          class="filter-btn"
          :class="{ active: tab === key }"
          @click="key === 'blank' ? blank() : (tab = key)"
        >
          {{ label }}
        </button>
      </div>

      <section
        v-if="tab === 'describe'"
        class="card space-y-3"
      >
        <template v-if="session.hasAiKey">
          <p class="text-sm text-gray-600">
            Say what you're in the mood for, what's in the fridge, or a dish to recreate.
          </p>
          <div class="flex gap-2">
            <textarea
              v-model="prompt"
              class="input"
              rows="3"
              placeholder="Something with chicken thighs and gochujang, one pan, ready in 30 minutes"
            />
            <MicButton @text="(t) => (prompt = (prompt ? prompt + ' ' : '') + t)" />
          </div>
          <div class="flex flex-wrap gap-2">
            <button
              v-demo-lock
              class="btn-primary"
              :disabled="!prompt.trim() || !!busy"
              @click="write()"
            >
              {{ busy === 'generate' ? 'Writing…' : 'Write the recipe' }}
            </button>
            <button
              v-demo-lock
              class="btn-secondary"
              :disabled="!prompt.trim() || !!busy"
              @click="brainstorm"
            >
              {{ busy === 'ideas' ? 'Thinking…' : 'Brainstorm ideas' }}
            </button>
          </div>
          <ul
            v-if="ideas"
            class="divide-y rounded-lg border"
          >
            <li
              v-for="idea in ideas"
              :key="idea.title"
              class="flex items-start justify-between gap-3 p-3"
            >
              <div>
                <div class="font-medium">
                  {{ idea.emoji }} {{ idea.title }}
                </div>
                <div class="text-sm text-gray-600">
                  {{ idea.pitch }}
                </div>
              </div>
              <RouterLink
                v-if="idea.existing_slug"
                :to="`/r/${idea.existing_slug}`"
                class="btn-secondary btn-sm shrink-0"
              >
                You have this
              </RouterLink>
              <button
                v-else
                v-demo-lock
                class="btn-primary btn-sm shrink-0"
                :disabled="!!busy"
                @click="write(`${idea.title}: ${idea.pitch}`)"
              >
                Write it
              </button>
            </li>
          </ul>
        </template>
        <p
          v-else
          class="text-gray-700"
        >
          Writing recipes with AI uses your own Anthropic API key. <RouterLink
            to="/settings"
            class="font-medium text-herb-600 underline"
          >
            Add it in Settings
          </RouterLink>.
        </p>
      </section>

      <form
        v-if="tab === 'link'"
        class="card space-y-3"
        @submit.prevent="fromLink"
      >
        <p class="text-sm text-gray-600">
          Paste a recipe page. Most recipe sites publish the recipe in a standard format, which is imported as-is; other pages are read by the assistant (needs your key).
        </p>
        <input
          v-model="url"
          type="url"
          class="input"
          placeholder="https://…"
          required
        >
        <button
          v-demo-lock
          class="btn-primary"
          :disabled="!!busy"
        >
          {{ busy === 'link' ? 'Importing…' : 'Import' }}
        </button>
      </form>

      <section
        v-if="tab === 'photo'"
        class="card space-y-3"
      >
        <template v-if="session.hasAiKey">
          <p class="text-sm text-gray-600">
            A photo of a cookbook page or recipe card.
          </p>
          <input
            v-demo-lock
            type="file"
            accept="image/*"
            capture="environment"
            :disabled="!!busy"
            @change="fromPhoto"
          >
          <p
            v-if="busy === 'photo'"
            class="text-sm text-gray-600"
          >
            Reading the photo…
          </p>
        </template>
        <p v-else>
          Reading photos uses your own Anthropic API key. <RouterLink
            to="/settings"
            class="font-medium text-herb-600 underline"
          >
            Add it in Settings
          </RouterLink>.
        </p>
      </section>

      <form
        v-if="tab === 'markdown'"
        class="card space-y-3"
        @submit.prevent="fromMarkdown"
      >
        <p class="text-sm text-gray-600">
          The cookbook's original format: a ## title, the Servings/Prep/Cook line, an ingredients table, a numbered method and a grocery list.
        </p>
        <textarea
          v-model="markdown"
          class="input font-mono text-sm"
          rows="14"
          placeholder="## 🍝 Title&#10;&#10;**Servings:** 4 | **Prep:** 10 min | **Cook:** 20 min&#10;&#10;### Ingredients&#10;| Group | Item | Amount |&#10;…"
        />
        <button
          v-demo-lock
          class="btn-primary"
          :disabled="!!busy"
        >
          Add recipe
        </button>
      </form>
    </template>

    <section
      v-else
      class="card"
    >
      <p
        v-if="via"
        class="mb-4 rounded-lg bg-violet-50 p-3 text-sm text-violet-900"
      >
        <template v-if="via === 'jsonld'">
          Imported from the page's recipe data. Check it over and save.
        </template>
        <template v-else>
          ✨ Written by the assistant. Check amounts and steps before you cook it; nothing is saved until you press Save.
        </template>
      </p>
      <RecipeEditor
        :initial="draft"
        :saving="saving"
        @save="save"
        @cancel="draft = null"
      />
    </section>
  </main>
</template>
