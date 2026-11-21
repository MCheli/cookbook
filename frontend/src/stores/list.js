import { defineStore } from 'pinia'
import { api } from '@/api'

/** This week's shopping list (signed in), shared by the header badge and the list page. */
export const useList = defineStore('list', {
  state: () => ({ list: null, loading: false }),
  getters: {
    recipeIds: (s) => new Set((s.list?.recipes ?? []).map((r) => r.recipe_id)),
    count: (s) => s.list?.recipes?.length ?? 0,
  },
  actions: {
    async load() {
      this.loading = true
      try {
        this.list = (await api.get('/lists/current')).data
      } finally {
        this.loading = false
      }
    },
    async addRecipe(recipeId, servingsFactor = 1) {
      this.list = (await api.post('/lists/current/recipes', { recipe_id: recipeId, servings_factor: servingsFactor })).data
    },
    async removeRecipe(recipeId) {
      this.list = (await api.delete(`/lists/current/recipes/${recipeId}`)).data
    },
    async setFactor(recipeId, factor) {
      this.list = (await api.patch(`/lists/current/recipes/${recipeId}`, { servings_factor: factor })).data
    },
    async patchItem(itemId, patch) {
      this.list = (await api.patch(`/lists/current/items/${itemId}`, patch)).data
    },
    async deleteItem(itemId) {
      this.list = (await api.delete(`/lists/current/items/${itemId}`)).data
    },
    async addItem(item) {
      this.list = (await api.post('/lists/current/items', item)).data
    },
    async addRegulars() {
      this.list = (await api.post('/lists/current/regulars')).data
    },
    async complete() {
      this.list = (await api.post('/lists/current/complete')).data
    },
    async clear() {
      this.list = (await api.post('/lists/current/clear')).data
    },
  },
})
