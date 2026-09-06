<template>
  <div class="nuxt-swagger-ui-viewer">
    <div v-if="error" class="nuxt-swagger-ui-error">
      Failed to load API explorer: {{ error }}
    </div>
    <div v-else-if="!loaded" class="nuxt-swagger-ui-loading">
      Loading API explorer…
    </div>
    <div ref="containerRef" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useCookie, useRuntimeConfig } from '#imports'

declare global {
  interface Window {
    SwaggerUIBundle?: any
    SwaggerUIStandalonePreset?: any
  }
}

const props = withDefaults(
  defineProps<{
    specUrl?: string
    swaggerOptions?: Record<string, any>
  }>(),
  {
    specUrl: undefined,
    swaggerOptions: undefined,
  },
)

const config = (useRuntimeConfig().public as any).swaggerUi ?? {}
const containerRef = ref<HTMLElement | null>(null)
const loaded = ref(false)
const error = ref<string | null>(null)

function loadStylesheet(href: string) {
  if (document.querySelector(`link[data-nuxt-swagger-ui="${href}"]`)) return
  const link = document.createElement('link')
  link.rel = 'stylesheet'
  link.href = href
  link.setAttribute('data-nuxt-swagger-ui', href)
  document.head.appendChild(link)
}

function loadScript(src: string, isLoaded: () => boolean) {
  return new Promise<void>((resolve, reject) => {
    const existing = document.querySelector(`script[data-nuxt-swagger-ui="${src}"]`)
    if (existing) {
      if (isLoaded()) {
        resolve()
      }
      else {
        existing.addEventListener('load', () => resolve())
        existing.addEventListener('error', () => reject(new Error(`Failed to load ${src}`)))
      }
      return
    }

    const script = document.createElement('script')
    script.src = src
    script.setAttribute('data-nuxt-swagger-ui', src)
    script.onload = () => resolve()
    script.onerror = () => reject(new Error(`Failed to load ${src}`))
    document.head.appendChild(script)
  })
}

onMounted(async () => {
  try {
    // Vendored locally by scripts/copy-swagger-bundle.mjs (postinstall) -
    // keeps the dashboard fully self-hosted/offline instead of pulling from
    // a CDN.
    const base = useRuntimeConfig().app.baseURL
    loadStylesheet(`${base}vendor/swagger/swagger-ui.css`)
    await loadScript(`${base}vendor/swagger/swagger-ui-bundle.js`, () => !!window.SwaggerUIBundle)
    await loadScript(`${base}vendor/swagger/swagger-ui-standalone-preset.js`, () => !!window.SwaggerUIStandalonePreset)

    if (!window.SwaggerUIBundle || !window.SwaggerUIStandalonePreset) {
      throw new Error('Swagger UI failed to attach to window')
    }

    const spec = props.specUrl || config.specUrl
    const opts = props.swaggerOptions || config.swaggerOptions || {}

    window.SwaggerUIBundle({
      url: spec,
      domNode: containerRef.value,
      presets: [window.SwaggerUIBundle.presets.apis, window.SwaggerUIStandalonePreset],
      plugins: [window.SwaggerUIBundle.plugins.DownloadUrl],
      layout: 'StandaloneLayout',
      // Reuse the dashboard's own JWT cookie so "Try it out" works against
      // protected endpoints without re-entering a token in Swagger's own
      // Authorize dialog - mirrors useApi.ts's onRequest bearer attachment.
      requestInterceptor: (req: any) => {
        const token = useCookie<string | null>('bottle_suite_token').value
        if (token) {
          req.headers.Authorization = `Bearer ${token}`
        }
        return req
      },
      ...opts,
    })
    loaded.value = true
  }
  catch (err: any) {
    error.value = err?.message ?? String(err)
  }
})
</script>

<style scoped>
.nuxt-swagger-ui-viewer {
  height: 100%;
  overflow: auto;
}

.nuxt-swagger-ui-loading,
.nuxt-swagger-ui-error {
  padding: 2rem;
  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  color: #666;
}

.nuxt-swagger-ui-error {
  color: #c0392b;
}
</style>
