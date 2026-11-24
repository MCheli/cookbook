import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'

import App from './App.vue'
import { routes, installGuards } from './router'
import { vDemoLock } from './directives/demoLock'
import { clearPrintArea } from './lib/print'
import './assets/main.css'

const app = createApp(App)
const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: (to, from, saved) => saved || (to.path !== from.path ? { top: 0 } : undefined),
})
installGuards(router)
router.afterEach(clearPrintArea)
app.use(createPinia())
app.directive('demo-lock', vDemoLock)
app.use(router)
app.mount('#app')
