<script setup>
import { nextTick, ref, watch } from 'vue'
import { api, errorMessage } from '@/api'
import { useSession } from '@/stores/session'
import { useList } from '@/stores/list'
import MicButton from '@/components/MicButton.vue'
import { inlineMd } from '@/lib/format'

const props = defineProps({
  threadId: { type: String, default: null },
  recipeSlug: { type: String, default: null },
  compact: { type: Boolean, default: false },
})
const emit = defineEmits(['thread'])
const session = useSession()
const list = useList()

const thread = ref(null)
const text = ref('')
const sending = ref(false)
const error = ref('')
const scroller = ref(null)

async function load(id) {
  thread.value = id ? (await api.get(`/ai/chat/threads/${id}`)).data : null
  scrollDown()
}
watch(() => props.threadId, load, { immediate: true })

function scrollDown() {
  nextTick(() => scroller.value && (scroller.value.scrollTop = scroller.value.scrollHeight))
}

const STARTERS = [
  'What should I make this week?',
  'Something new with chicken thighs',
  'What can I make with what I have?',
  'Put two quick dinners on my list',
]

async function send(message) {
  const msg = (message ?? text.value).trim()
  if (!msg || sending.value) return
  sending.value = true
  error.value = ''
  const pending = { id: 'pending', role: 'user', text: msg }
  thread.value = thread.value ? { ...thread.value, messages: [...thread.value.messages, pending] } : { messages: [pending] }
  text.value = ''
  scrollDown()
  try {
    const { data } = await api.post('/ai/chat', { message: msg, thread_id: thread.value?.id || props.threadId || null, recipe_slug: props.recipeSlug })
    thread.value = data
    emit('thread', data)
    if (data.messages.at(-1)?.actions?.some((a) => a.type === 'list')) list.load()
  } catch (e) {
    error.value = errorMessage(e, 'The assistant is unavailable right now.')
    thread.value.messages = thread.value.messages.filter((m) => m.id !== 'pending')
    text.value = msg
  } finally {
    sending.value = false
    scrollDown()
  }
}
</script>

<template>
  <div class="flex h-full min-h-0 flex-col">
    <div
      ref="scroller"
      class="min-h-0 flex-1 space-y-3 overflow-y-auto p-4"
    >
      <template v-if="!thread?.messages?.length">
        <p class="text-sm text-gray-600">
          Ask about a recipe, plan the week, or have it write something new. It can search your cookbook, save drafts and update your current order.
          <span v-if="recipeSlug"> It can see the recipe you're on.</span>
        </p>
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="s in STARTERS"
            :key="s"
            v-demo-lock
            class="rounded-full bg-white px-3 py-1 text-xs text-violet-800 ring-1 ring-violet-200 hover:bg-violet-50"
            :disabled="!session.hasAiKey"
            @click="send(s)"
          >
            {{ s }}
          </button>
        </div>
      </template>
      <div
        v-for="m in thread?.messages ?? []"
        :key="m.id"
        :class="m.role === 'user' ? 'flex justify-end' : ''"
      >
        <div
          class="max-w-[85%] whitespace-pre-line rounded-2xl px-3.5 py-2 text-[0.95rem]"
          :class="m.role === 'user' ? 'bg-herb-600 text-white' : 'bg-gray-100 text-gray-900'"
          v-html="inlineMd(m.text)"
        />
        <div
          v-if="m.actions?.length"
          class="mt-2 space-y-1.5"
        >
          <template
            v-for="(a, n) in m.actions"
            :key="n"
          >
            <RouterLink
              v-if="a.type === 'draft'"
              :to="`/r/${a.slug}`"
              class="block max-w-[85%] rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-sm hover:bg-violet-100"
            >
              ✨ Draft saved: <strong>{{ a.emoji }} {{ a.title }}</strong><span v-if="a.based_on"> (version of {{ a.based_on }})</span> — review it
            </RouterLink>
            <div
              v-else-if="a.type === 'list'"
              class="max-w-[85%] rounded-lg border border-herb-200 bg-herb-50 px-3 py-2 text-sm"
            >
              🛒 {{ a.message }} · <RouterLink
                to="/list"
                class="underline"
              >
                open list
              </RouterLink>
            </div>
          </template>
        </div>
      </div>
      <div
        v-if="sending"
        class="text-sm text-gray-500"
      >
        Thinking…
      </div>
      <p
        v-if="error"
        class="text-sm text-red-700"
      >
        {{ error }}
      </p>
    </div>
    <div class="border-t bg-white p-3 safe-bottom">
      <form
        v-if="session.hasAiKey && !session.demo"
        class="flex gap-2"
        @submit.prevent="send()"
      >
        <input
          v-model="text"
          class="input"
          :placeholder="recipeSlug ? 'Ask about this recipe…' : 'Ask anything about cooking…'"
          :disabled="sending"
          enterkeyhint="send"
        >
        <MicButton @text="(t) => { text = (text ? text + ' ' : '') + t }" />
        <button
          class="btn-primary"
          :disabled="sending || !text.trim()"
        >
          Send
        </button>
      </form>
      <p
        v-else-if="session.demo"
        class="text-sm text-gray-600"
      >
        In the demo you can read a saved conversation. Real chats run on each person's own Anthropic key.
      </p>
      <p
        v-else
        class="text-sm text-gray-700"
      >
        Chat uses your own Anthropic API key. <RouterLink
          to="/settings"
          class="font-medium text-herb-600 underline"
        >
          Add it in Settings
        </RouterLink>.
      </p>
    </div>
  </div>
</template>
