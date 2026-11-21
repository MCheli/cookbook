<script setup>
import { computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useSession } from '@/stores/session'
import { useList } from '@/stores/list'
import AppHeader from '@/components/AppHeader.vue'
import DemoBanner from '@/components/DemoBanner.vue'
import ChatFab from '@/components/ChatFab.vue'
import ToastHost from '@/components/ToastHost.vue'
import { useUpdateCheck } from '@/lib/updateCheck'

const session = useSession()
const list = useList()
const route = useRoute()
const bare = computed(() => route.meta.bare)
const { updateReady, reload } = useUpdateCheck()

onMounted(() => session.load())
watch(
  () => session.user?.id,
  (id) => {
    if (id) list.load().catch(() => {})
  },
  { immediate: true },
)
</script>

<template>
  <div
    v-if="updateReady"
    class="flex items-center justify-center gap-3 bg-herb-700 px-3 py-2 text-sm text-white print:hidden"
    role="status"
  >
    A new version of the cookbook is available.
    <button
      class="rounded bg-white px-2.5 py-0.5 font-medium text-herb-700"
      @click="reload"
    >
      Refresh
    </button>
  </div>
  <DemoBanner v-if="session.demo && !bare" />
  <AppHeader v-if="!bare" />
  <RouterView />
  <ChatFab v-if="session.signedIn && !bare && route.name !== 'chat'" />
  <ToastHost />
</template>
