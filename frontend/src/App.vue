<script setup>
import { computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useSession } from '@/stores/session'
import { useList } from '@/stores/list'
import AppHeader from '@/components/AppHeader.vue'
import DemoBanner from '@/components/DemoBanner.vue'
import ChatFab from '@/components/ChatFab.vue'
import ToastHost from '@/components/ToastHost.vue'

const session = useSession()
const list = useList()
const route = useRoute()
const bare = computed(() => route.meta.bare)

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
  <DemoBanner v-if="session.demo && !bare" />
  <AppHeader v-if="!bare" />
  <RouterView />
  <ChatFab v-if="session.signedIn && !bare && route.name !== 'chat'" />
  <ToastHost />
</template>
