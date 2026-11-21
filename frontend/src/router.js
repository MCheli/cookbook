import { useSession } from '@/stores/session'

// Public pages are the cookbook itself; the rest need a sign-in.
export const routes = [
  { path: '/', name: 'home', component: () => import('@/views/HomeView.vue'), meta: { public: true } },
  { path: '/r/:slug', name: 'recipe', component: () => import('@/views/RecipeView.vue'), meta: { public: true }, props: true },
  { path: '/grocery', name: 'grocery', component: () => import('@/views/GroceryPreviewView.vue'), meta: { public: true } },
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true, bare: true } },
  { path: '/list', name: 'list', component: () => import('@/views/ListView.vue') },
  { path: '/products', name: 'products', component: () => import('@/views/ProductsView.vue') },
  { path: '/new', name: 'new', component: () => import('@/views/NewRecipeView.vue') },
  { path: '/r/:slug/edit', name: 'edit', component: () => import('@/views/EditRecipeView.vue'), props: true },
  { path: '/chat', name: 'chat', component: () => import('@/views/ChatView.vue') },
  { path: '/history', name: 'history', component: () => import('@/views/HistoryView.vue') },
  { path: '/settings', name: 'settings', component: () => import('@/views/SettingsView.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export function installGuards(router) {
  router.beforeEach(async (to) => {
    const session = useSession()
    await session.load()
    if (to.meta.public || session.signedIn) return true
    return { name: 'login', query: { next: to.fullPath } }
  })
}
