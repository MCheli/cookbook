<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, errorMessage } from '@/api'
import { useSession } from '@/stores/session'

const session = useSession()
const route = useRoute()
const router = useRouter()
const next = computed(() => (typeof route.query.next === 'string' && route.query.next.startsWith('/') ? route.query.next : '/'))
const email = ref('')
const password = ref('')
const error = ref(
  route.query.error === 'unverified' ? 'That Google account has no verified email.' : route.query.error ? "Google sign-in didn't finish. Try again." : '',
)
const busy = ref(false)

async function passwordLogin() {
  busy.value = true
  try {
    session.setUser((await api.post('/auth/login', { email: email.value, password: password.value })).data)
    router.push(next.value)
  } catch (e) {
    error.value = errorMessage(e, 'Sign-in failed.')
  } finally {
    busy.value = false
  }
}

async function enterDemo() {
  busy.value = true
  try {
    session.setUser((await api.post('/auth/demo')).data)
    router.push('/list')
  } catch (e) {
    error.value = errorMessage(e, 'The demo is unavailable right now.')
  } finally {
    busy.value = false
  }
}

const chips = ['Instant Pot · Crockpot · Stovetop', 'One combined grocery list', 'Add to your Whole Foods cart', 'AI remixes on your own key', 'Prints one recipe per page']
</script>

<template>
  <div class="flex min-h-screen flex-col md:flex-row">
    <section class="relative overflow-hidden bg-gradient-to-br from-herb-800 via-herb-700 to-[#0f1f0c] px-6 py-10 text-white md:w-[55%] md:px-12 md:py-16">
      <div class="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-[#7cc46a]/20 blur-3xl" />
      <div class="pointer-events-none absolute -bottom-32 left-10 h-80 w-80 rounded-full bg-violet-500/20 blur-3xl" />
      <RouterLink
        to="/"
        class="relative flex items-center gap-2 text-xl font-bold"
      >
        <img
          src="/favicon.svg"
          alt=""
          class="h-8 w-8"
        > Cookbook
      </RouterLink>
      <h1 class="relative mt-8 max-w-xl text-3xl font-bold leading-tight md:mt-14 md:text-4xl">
        Your recipes, your grocery orders, and a sous-chef that knows both.
      </h1>
      <p class="relative mt-4 max-w-xl text-white/80">
        Pick a few dinners and get one combined list, matched to the Whole Foods products you actually buy.
        Add each item to your Whole Foods cart with a tap, print the recipes, and ask the assistant to swap, scale or invent; it runs on your own Anthropic key.
      </p>
      <div class="relative mt-10 hidden max-w-xl grid-cols-2 gap-4 md:grid">
        <div class="animate-[float_6s_ease-in-out_infinite] rounded-2xl border border-white/15 bg-white/10 p-4 backdrop-blur motion-reduce:animate-none">
          <span class="rounded-full bg-white/20 px-2 py-0.5 text-[11px]">Instant Pot</span>
          <div class="mt-2 font-semibold">
            🌶️ Jerk Chicken &amp; Rice
          </div>
          <div class="text-xs text-white/70">
            4–6 servings | Prep: 5 min
          </div>
        </div>
        <div class="mt-8 animate-[float_7s_ease-in-out_infinite] rounded-2xl border border-white/15 bg-white/10 p-4 text-sm backdrop-blur motion-reduce:animate-none">
          <div class="mb-1 text-xs uppercase tracking-wide text-white/60">
            Protein
          </div>
          <div class="flex justify-between">
            <span>Chicken thighs</span><span class="text-white/70">2 lb</span>
          </div>
          <div class="flex justify-between">
            <span>Sausage links</span><span class="text-white/70">12 oz</span>
          </div>
          <div class="mt-2 rounded-md bg-[#ff9900] px-2 py-1 text-center text-xs font-semibold">
            Add to Whole Foods cart
          </div>
        </div>
        <div class="col-span-2 animate-[float_8s_ease-in-out_infinite] rounded-2xl border border-violet-300/30 bg-violet-500/15 p-4 text-sm backdrop-blur motion-reduce:animate-none">
          <div class="text-white/70">
            “I'm out of heavy cream.”
          </div>
          <div class="mt-1">
            ✨ Swapped in 1 cup half-and-half; parmesan goes in off the heat so it doesn't split.
          </div>
        </div>
      </div>
      <div class="relative mt-8 hidden flex-wrap gap-2 md:flex">
        <span
          v-for="c in chips"
          :key="c"
          class="rounded-full border border-white/20 px-3 py-1 text-xs text-white/80"
        >{{ c }}</span>
      </div>
    </section>

    <section class="flex flex-1 items-center justify-center bg-white px-6 py-10">
      <div class="w-full max-w-sm">
        <template v-if="session.demo">
          <span class="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800">Live demo</span>
          <h2 class="mt-4 text-2xl font-semibold">
            Cook along with Claudius Banks
          </h2>
          <p class="mt-2 text-gray-600">
            Claudius is made up: their week's list, products, history and assistant chats are generated, and nothing here can be changed.
          </p>
          <button
            class="btn-primary mt-6 w-full py-3 text-base"
            :disabled="busy"
            @click="enterDemo"
          >
            Enter the demo
          </button>
        </template>
        <template v-else>
          <h2 class="text-2xl font-semibold">
            Sign in
          </h2>
          <p class="mt-1 text-sm text-gray-600">
            Anyone can browse the recipes. Sign in to keep your own recipes, lists and products.
          </p>
          <a
            v-if="session.googleConfigured"
            :href="session.googleLoginUrl(next)"
            class="mt-6 flex w-full items-center justify-center gap-3 rounded-md border border-gray-300 bg-white px-4 py-3 font-medium shadow-sm hover:bg-gray-50"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 48 48"
            ><path
              fill="#FFC107"
              d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"
            /><path
              fill="#FF3D00"
              d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"
            /><path
              fill="#4CAF50"
              d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z"
            /><path
              fill="#1976D2"
              d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"
            /></svg>
            Continue with Google
          </a>
          <form
            v-if="session.passwordLogin"
            class="mt-6 space-y-3"
            @submit.prevent="passwordLogin"
          >
            <input
              v-model="email"
              class="input"
              type="email"
              placeholder="Email"
              autocomplete="username"
            >
            <input
              v-model="password"
              class="input"
              type="password"
              placeholder="Password"
              autocomplete="current-password"
            >
            <button
              class="btn-primary w-full"
              :disabled="busy"
            >
              Sign in
            </button>
          </form>
          <a
            v-if="session.demoUrl"
            :href="session.demoUrl"
            class="mt-8 block rounded-xl border border-gray-200 p-4 hover:border-herb-400"
          >
            <div class="font-medium">Just looking? Try the live demo →</div>
            <div class="text-sm text-gray-600">A made-up cook's week: list, Whole Foods products, history and assistant chats. Read-only, no sign-in.</div>
          </a>
        </template>
        <p
          v-if="error"
          class="mt-4 text-sm text-red-700"
        >
          {{ error }}
        </p>
        <p class="mt-10 text-xs text-gray-400">
          <RouterLink
            to="/"
            class="underline"
          >
            Browse recipes
          </RouterLink> · Built by <a
            href="https://www.markcheli.com"
            class="underline"
          >Mark Cheli</a>
        </p>
      </div>
    </section>
  </div>
</template>

<style>
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}
</style>
