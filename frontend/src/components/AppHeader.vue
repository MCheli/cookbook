<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { useSession } from '@/stores/session'
import { useList } from '@/stores/list'

const session = useSession()
const list = useList()
const route = useRoute()
const open = ref(false)

const links = [
  { to: '/', label: 'Recipes', name: 'home' },
  { to: '/list', label: 'This week', name: 'list', badge: true },
  { to: '/new', label: 'New recipe', name: 'new' },
  { to: '/chat', label: 'Chat', name: 'chat' },
  { to: '/products', label: 'Products', name: 'products' },
  { to: '/history', label: 'History', name: 'history' },
  { to: '/settings', label: 'Settings', name: 'settings' },
]
</script>

<template>
  <header class="bg-herb-600 text-white">
    <div class="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3 sm:px-6">
      <RouterLink
        to="/"
        class="flex items-center gap-2 text-2xl font-bold tracking-tight"
      >
        <img
          src="/favicon.svg"
          alt=""
          class="h-7 w-7"
        >
        Cookbook
      </RouterLink>
      <nav
        v-if="session.signedIn"
        class="ml-auto hidden items-center gap-1 md:flex"
      >
        <RouterLink
          v-for="l in links"
          :key="l.to"
          :to="l.to"
          class="relative rounded-md px-3 py-1.5 text-sm font-medium text-white/90 hover:bg-white/10"
          :class="{ 'bg-white/15 text-white': route.name === l.name }"
        >
          {{ l.label }}
          <span
            v-if="l.badge && list.count"
            class="ml-1 rounded-full bg-white px-1.5 text-xs font-semibold text-herb-700"
          >{{ list.count }}</span>
        </RouterLink>
      </nav>
      <div
        v-else
        class="ml-auto"
      >
        <RouterLink
          :to="{ name: 'login', query: { next: route.fullPath } }"
          class="rounded-md bg-white/15 px-3 py-1.5 text-sm font-medium hover:bg-white/25"
        >
          Sign in
        </RouterLink>
      </div>
      <button
        v-if="session.signedIn"
        class="ml-auto rounded-md p-2 hover:bg-white/10 md:hidden"
        aria-label="Menu"
        @click="open = !open"
      >
        <svg
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        ><path d="M4 6h16M4 12h16M4 18h16" /></svg>
      </button>
    </div>
    <nav
      v-if="open && session.signedIn"
      class="border-t border-white/10 px-4 pb-3 md:hidden"
      @click="open = false"
    >
      <RouterLink
        v-for="l in links"
        :key="l.to"
        :to="l.to"
        class="block rounded-md px-3 py-2 text-base font-medium hover:bg-white/10"
        :class="{ 'bg-white/15': route.name === l.name }"
      >
        {{ l.label }}
        <span
          v-if="l.badge && list.count"
          class="ml-1 rounded-full bg-white px-1.5 text-xs font-semibold text-herb-700"
        >{{ list.count }}</span>
      </RouterLink>
    </nav>
  </header>
</template>
