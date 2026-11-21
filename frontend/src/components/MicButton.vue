<script setup>
import { onBeforeUnmount, ref } from 'vue'

// Speech to text with the browser's own recognizer (Safari and Chrome). Where it isn't available
// (some Home Screen web apps), the button explains the keyboard's dictation key instead.
const emit = defineEmits(['text'])
const SR = typeof window !== 'undefined' ? window.SpeechRecognition || window.webkitSpeechRecognition : null
const listening = ref(false)
const hint = ref('')
let rec = null

function start() {
  if (!SR) {
    hint.value = 'Voice input isn\'t available here. Tap the microphone on your keyboard to dictate.'
    setTimeout(() => (hint.value = ''), 5000)
    return
  }
  if (listening.value) {
    rec?.stop()
    return
  }
  rec = new SR()
  rec.lang = navigator.language || 'en-US'
  rec.interimResults = false
  rec.continuous = false
  rec.onresult = (e) => {
    const text = Array.from(e.results).map((r) => r[0].transcript).join(' ').trim()
    if (text) emit('text', text)
  }
  rec.onerror = (e) => {
    if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
      hint.value = 'Microphone access was refused. Allow it in Settings, or use the keyboard\'s dictation key.'
      setTimeout(() => (hint.value = ''), 6000)
    }
  }
  rec.onend = () => (listening.value = false)
  listening.value = true
  try {
    rec.start()
  } catch {
    listening.value = false
  }
}
onBeforeUnmount(() => rec?.abort())
</script>

<template>
  <span class="relative">
    <button
      type="button"
      class="btn h-full border px-3"
      :class="listening ? 'animate-pulse border-red-400 bg-red-50 text-red-700' : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'"
      :aria-label="listening ? 'Stop listening' : 'Speak'"
      :title="listening ? 'Listening… tap to stop' : 'Speak'"
      @click="start"
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
      ><rect
        x="9"
        y="2"
        width="6"
        height="12"
        rx="3"
      /><path d="M5 10a7 7 0 0 0 14 0M12 17v5M8 22h8" /></svg>
    </button>
    <span
      v-if="hint"
      class="absolute bottom-full right-0 z-20 mb-2 w-64 rounded-md bg-gray-900 px-3 py-2 text-xs text-white shadow"
    >{{ hint }}</span>
  </span>
</template>
