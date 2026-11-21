<script setup>
import { ref } from 'vue'
import { api, errorMessage } from '@/api'
import { useSession } from '@/stores/session'
import MicButton from '@/components/MicButton.vue'

const props = defineProps({ recipe: { type: Object, required: true } })
const emit = defineEmits(['result'])
const session = useSession()

const instruction = ref('')
const busy = ref(false)
const error = ref('')

const QUICK = [
  "I'm missing an ingredient…",
  'Make it spicier',
  'Make it lighter',
  'Instant Pot version',
  'Crockpot version',
  'Serves 2',
  'Vegetarian version',
  'Use what I have: ',
]

function quick(q) {
  instruction.value = q.endsWith('…') ? "I don't have " : q
  if (!q.endsWith('…') && !q.endsWith(': ')) run()
}

async function run() {
  if (!instruction.value.trim()) return
  busy.value = true
  error.value = ''
  try {
    const { data } = await api.post(`/ai/recipes/${props.recipe.id}/adapt`, { instruction: instruction.value })
    emit('result', data)
  } catch (e) {
    error.value = errorMessage(e, 'The assistant could not change this recipe.')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="rounded-xl border border-violet-200 bg-violet-50/60 p-4">
    <div class="mb-2 flex items-center gap-2">
      <span class="ai-badge">✨ Assistant</span>
      <span class="text-sm text-gray-600">Change this recipe for tonight, or keep it as a new version.</span>
    </div>
    <template v-if="session.hasAiKey">
      <div class="mb-3 flex flex-wrap gap-1.5">
        <button
          v-for="q in QUICK"
          :key="q"
          v-demo-lock
          class="rounded-full bg-white px-3 py-1 text-xs text-violet-800 ring-1 ring-violet-200 hover:bg-violet-100"
          :disabled="busy"
          @click="quick(q)"
        >
          {{ q }}
        </button>
      </div>
      <form
        class="flex gap-2"
        @submit.prevent="run"
      >
        <input
          v-model="instruction"
          class="input"
          placeholder="e.g. I'm out of heavy cream, or make it with chicken thighs"
          :disabled="busy"
        >
        <MicButton @text="(t) => (instruction = (instruction ? instruction + ' ' : '') + t)" />
        <button
          v-demo-lock
          class="btn-primary whitespace-nowrap"
          :disabled="busy || !instruction.trim()"
        >
          {{ busy ? 'Thinking…' : 'Change it' }}
        </button>
      </form>
      <p
        v-if="error"
        class="mt-2 text-sm text-red-700"
      >
        {{ error }}
      </p>
    </template>
    <p
      v-else
      class="text-sm text-gray-700"
    >
      AI features run on your own Anthropic API key.
      <RouterLink
        to="/settings"
        class="font-medium text-herb-600 underline"
      >
        Add your key in Settings
      </RouterLink>
      to change recipes, brainstorm new ones and chat while you cook.
    </p>
  </section>
</template>
