<template>
  <div class="space-y-6 h-full flex flex-col">
    <PageHeader title="API Explorer" description="Try out this server's REST API directly from the browser" />

    <LoadingRows v-if="loading" variant="card" :count="4" />
    <EmptyState
      v-else-if="disabled"
      icon="i-lucide-flask-conical"
      message="API docs are disabled. Enable [openapi] in bottle_suite.toml to turn them on."
    />
    <ClientOnly v-else class="flex-1 min-h-0">
      <SwaggerUIViewer :spec-url="specUrl" />
    </ClientOnly>
  </div>
</template>

<script setup lang="ts">
// Swagger UI has no equivalent of Redoc's theme option (see api-docs.vue) -
// it ships its own fixed light-mode look, so no colorMode/brand-token wiring
// here.
definePageMeta({ title: 'API Explorer' })

const runtimeConfig = useRuntimeConfig()
const { showError } = useToastError()

const loading = ref(true)
const disabled = ref(false)

const specUrl = `${runtimeConfig.public.apiBase}/openapi.json`

onMounted(async () => {
  try {
    const api = useApi()
    await api('/openapi.json')
  } catch (e: any) {
    if (e?.response?.status === 404) {
      disabled.value = true
    } else {
      showError(e?.data?.message ?? 'Failed to load API explorer')
    }
  } finally {
    loading.value = false
  }
})
</script>
