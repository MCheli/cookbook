<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, errorMessage } from '@/api'
import RecipeEditor from '@/components/RecipeEditor.vue'
import { toast } from '@/lib/toast'

const props = defineProps({ slug: { type: String, required: true } })
const router = useRouter()
const recipe = ref(null)
const saving = ref(false)

onMounted(async () => {
  try {
    const { data } = await api.get(`/recipes/${props.slug}`)
    if (!data.can_edit) {
      router.replace(`/r/${props.slug}`)
      return
    }
    recipe.value = data
  } catch (e) {
    toast(errorMessage(e), 'error')
  }
})

async function save(payload) {
  saving.value = true
  try {
    const { data } = await api.put(`/recipes/${recipe.value.id}`, payload)
    toast('Saved')
    router.push(`/r/${data.slug}`)
  } catch (e) {
    toast(errorMessage(e), 'error')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <main class="mx-auto max-w-4xl px-4 py-6 sm:px-6">
    <RouterLink
      :to="`/r/${slug}`"
      class="text-sm text-herb-600 hover:underline"
    >
      ← Back to the recipe
    </RouterLink>
    <section
      v-if="recipe"
      class="card mt-3"
    >
      <h2 class="mb-4 text-xl font-semibold">
        Edit {{ recipe.title }}
      </h2>
      <RecipeEditor
        :initial="recipe"
        :saving="saving"
        @save="save"
        @cancel="router.push(`/r/${slug}`)"
      />
    </section>
  </main>
</template>
