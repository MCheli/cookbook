import { defineStore } from 'pinia'
import { api } from '@/api'

let pending = null

/** Who is signed in, and what this deployment is (Google sign-in, demo). Loaded once. */
export const useSession = defineStore('session', {
  state: () => ({ user: null, config: null, loaded: false }),
  getters: {
    signedIn: (s) => !!s.user,
    demo: (s) => s.config?.demo_mode ?? false,
    demoUrl: (s) => s.config?.demo_url ?? null,
    googleConfigured: (s) => s.config?.google_configured ?? false,
    passwordLogin: (s) => s.config?.password_login ?? false,
    hasAiKey: (s) => !!s.user?.has_anthropic_key,
    isOwner: (s) => !!s.user?.is_owner,
  },
  actions: {
    load() {
      if (!pending) {
        pending = Promise.all([
          api.get('/auth/config').then((r) => (this.config = r.data)).catch(() => {
            this.config = { google_configured: false, demo_mode: false, demo_url: null }
          }),
          api.get('/auth/session').then((r) => (this.user = r.data.user)).catch(() => (this.user = null)),
        ]).finally(() => (this.loaded = true))
      }
      return pending
    },
    async refresh() {
      try {
        this.user = (await api.get('/auth/session')).data.user
      } catch {
        this.user = null
      }
    },
    setUser(user) {
      this.user = user
    },
    async logout() {
      try {
        await api.post('/auth/logout')
      } finally {
        this.user = null
      }
    },
    googleLoginUrl(next) {
      return '/api/auth/google/login' + (next ? `?next=${encodeURIComponent(next)}` : '')
    },
  },
})
