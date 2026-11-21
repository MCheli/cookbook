<script setup>
import { toasts } from '@/lib/toast'
</script>

<template>
  <div
    class="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4 safe-bottom"
    aria-live="polite"
  >
    <div
      v-for="t in toasts"
      :key="t.id"
      class="pointer-events-auto max-w-md rounded-lg px-4 py-2 text-sm text-white shadow-lg"
      :class="t.kind === 'error' ? 'bg-red-700' : 'bg-gray-900'"
    >
      {{ t.message }}
    </div>
  </div>
</template>
