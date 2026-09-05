<template>
  <div class="space-y-6 h-full flex flex-col">
    <PageHeader title="API Docs" description="Interactive reference for this server's REST API" />

    <LoadingRows v-if="loading" variant="card" :count="4" />
    <EmptyState
      v-else-if="disabled"
      icon="i-lucide-book-open-text"
      message="API docs are disabled. Enable [openapi] in bottle_suite.toml to turn them on."
    />
    <ClientOnly v-else class="flex-1 min-h-0">
      <RedocViewer :key="colorMode.value" :spec-url="specUrl" :redoc-options="redocOptions" />
    </ClientOnly>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ title: 'API Docs' })

const runtimeConfig = useRuntimeConfig()
const { showError } = useToastError()
const colorMode = useColorMode()

const loading = ref(true)
const disabled = ref(false)

const specUrl = `${runtimeConfig.public.apiBase}/openapi.json`

// Mirrors the "bottle glass" brand tokens in app/assets/css/main.css /
// app/app.config.ts - Redoc has no notion of the dashboard's CSS variables,
// so the relevant hexes are duplicated here for each color-mode variant.
const FONT_SANS = "'IBM Plex Sans', ui-sans-serif, system-ui, sans-serif"
const FONT_MONO = "'IBM Plex Mono', ui-monospace, 'SFMono-Regular', monospace"

const theme = computed(() => {
  const dark = colorMode.value === 'dark'
  return {
    colors: {
      primary: { main: dark ? '#ba772c' : '#d39145' },
      success: { main: dark ? '#7c9550' : '#95af6a' },
      error: { main: dark ? '#ae4f37' : '#c86851' },
      text: { primary: dark ? '#ede8dc' : '#1e1b14' },
    },
    typography: {
      fontFamily: FONT_SANS,
      headings: { fontFamily: FONT_SANS },
      code: { fontFamily: FONT_MONO },
    },
    sidebar: {
      backgroundColor: dark ? '#1b1e16' : '#ffffff',
      textColor: dark ? '#ede8dc' : '#1e1b14',
    },
    rightPanel: {
      backgroundColor: dark ? '#12140f' : '#1e1b14',
      textColor: dark ? '#ede8dc' : '#f2efe6',
    },
  }
})
const redocOptions = computed(() => ({ theme: theme.value }))

onMounted(async () => {
  try {
    const api = useApi()
    await api('/openapi.json')
  } catch (e: any) {
    if (e?.response?.status === 404) {
      disabled.value = true
    } else {
      showError(e?.data?.message ?? 'Failed to load API docs')
    }
  } finally {
    loading.value = false
  }
})
</script>
