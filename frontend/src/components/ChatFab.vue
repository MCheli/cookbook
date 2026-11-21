<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import ChatPanel from '@/components/ChatPanel.vue'

// The assistant on every page: a floating button that opens a chat sheet. On a recipe page the
// chat can see that recipe. A fresh conversation per recipe; the Chat page keeps them all.
const route = useRoute()
const open = ref(false)
const threadId = ref(null)
const recipeSlug = computed(() => (route.name === 'recipe' ? route.params.slug : null))
watch(recipeSlug, () => (threadId.value = null))
</script>

<template>
  <button
    v-if="!open"
    class="fixed bottom-5 right-5 z-30 flex h-14 w-14 items-center justify-center rounded-full bg-violet-600 text-2xl text-white shadow-lg hover:bg-violet-700 print:hidden"
    aria-label="Open the cooking assistant"
    title="Cooking assistant"
    @click="open = true"
  >
    ✨
  </button>
  <div
    v-if="open"
    class="fixed inset-0 z-40 bg-black/30 sm:bg-transparent print:hidden"
    @click.self="open = false"
  >
    <div class="absolute inset-x-0 bottom-0 flex h-[80vh] flex-col overflow-hidden rounded-t-2xl bg-white shadow-2xl sm:inset-x-auto sm:bottom-5 sm:right-5 sm:h-[34rem] sm:w-[26rem] sm:rounded-2xl">
      <div class="flex items-center justify-between border-b px-4 py-2.5">
        <span class="font-semibold">✨ Cooking assistant</span>
        <div class="flex items-center gap-3 text-sm">
          <button
            v-if="threadId"
            class="text-gray-500 hover:text-gray-800"
            @click="threadId = null"
          >
            New chat
          </button>
          <RouterLink
            to="/chat"
            class="text-gray-500 hover:text-gray-800"
            @click="open = false"
          >
            All chats
          </RouterLink>
          <button
            class="text-xl leading-none text-gray-400"
            aria-label="Close"
            @click="open = false"
          >
            ×
          </button>
        </div>
      </div>
      <ChatPanel
        :key="threadId || 'new'"
        :thread-id="threadId"
        :recipe-slug="recipeSlug"
        @thread="(t) => (threadId = t.id)"
      />
    </div>
  </div>
</template>
