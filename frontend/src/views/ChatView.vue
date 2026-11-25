<script setup>
import { onMounted, ref } from 'vue'
import { api } from '@/api'
import ChatPanel from '@/components/ChatPanel.vue'

const threads = ref([])
const current = ref(null)

async function load() {
  threads.value = (await api.get('/ai/chat/threads')).data
}
onMounted(async () => {
  await load()
  current.value = threads.value[0]?.id ?? null
})

function onThread(t) {
  current.value = t.id
  if (!threads.value.some((x) => x.id === t.id)) threads.value.unshift({ id: t.id, title: t.title, updated_at: t.updated_at })
}

async function remove(id) {
  if (!confirm('Delete this chat?')) return
  await api.delete(`/ai/chat/threads/${id}`)
  if (current.value === id) current.value = null
  await load()
}
</script>

<template>
  <main class="chat-page mx-auto flex max-w-6xl gap-4 px-4 py-4 sm:px-6">
    <aside class="hidden w-64 shrink-0 flex-col overflow-y-auto rounded-xl bg-white p-3 shadow md:flex">
      <button
        class="btn-primary btn-sm mb-3"
        @click="current = null"
      >
        + New chat
      </button>
      <div
        v-for="t in threads"
        :key="t.id"
        class="group flex items-center rounded-md"
        :class="t.id === current ? 'bg-herb-50' : 'hover:bg-gray-50'"
      >
        <button
          class="min-w-0 flex-1 truncate px-2 py-1.5 text-left text-sm"
          @click="current = t.id"
        >
          {{ t.title }}
        </button>
        <button
          v-demo-lock
          class="px-2 text-gray-300 opacity-0 hover:text-red-700 group-hover:opacity-100"
          aria-label="Delete chat"
          @click="remove(t.id)"
        >
          ✕
        </button>
      </div>
    </aside>
    <section class="flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl bg-white shadow">
      <div class="flex items-center justify-between border-b px-4 py-2.5 md:hidden">
        <select
          class="input w-auto py-1 text-sm"
          :value="current || ''"
          @change="current = $event.target.value || null"
        >
          <option value="">
            New chat
          </option>
          <option
            v-for="t in threads"
            :key="t.id"
            :value="t.id"
          >
            {{ t.title }}
          </option>
        </select>
      </div>
      <ChatPanel
        :key="current || 'new'"
        :thread-id="current"
        @thread="onThread"
      />
    </section>
  </main>
</template>
