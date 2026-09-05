<template>
  <div class="nuxt-redoc-viewer">
    <div v-if="error" class="nuxt-redoc-error">
      Failed to load API documentation: {{ error }}
    </div>
    <div v-else-if="!loaded" class="nuxt-redoc-loading">
      Loading API docs…
    </div>
    <div ref="containerRef" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRuntimeConfig } from '#imports'

declare global {
  interface Window {
    Redoc?: {
      init: (spec: string | object, options: Record<string, any>, el: HTMLElement | null) => void
    }
  }
}

const props = withDefaults(
  defineProps<{
    specUrl?: string
    redocOptions?: Record<string, any>
  }>(),
  {
    specUrl: undefined,
    redocOptions: undefined,
  },
)

const config = (useRuntimeConfig().public as any).redoc ?? {}
const containerRef = ref<HTMLElement | null>(null)
const loaded = ref(false)
const error = ref<string | null>(null)

function loadScript(src: string) {
  return new Promise<void>((resolve, reject) => {
    const existing = document.querySelector(`script[data-nuxt-redoc="${src}"]`)
    if (existing) {
      if (window.Redoc) {
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
    script.setAttribute('data-nuxt-redoc', src)
    script.onload = () => resolve()
    script.onerror = () => reject(new Error(`Failed to load ${src}`))
    document.head.appendChild(script)
  })
}

onMounted(async () => {
  try {
    // Vendored locally by scripts/copy-redoc-bundle.mjs (postinstall) instead
    // of fetched from a CDN - keeps the dashboard fully self-hosted/offline.
    const src = `${useRuntimeConfig().app.baseURL}vendor/redoc.standalone.js`
    await loadScript(src)

    const spec = props.specUrl || config.specUrl
    const opts = props.redocOptions || config.redocOptions || {}

    if (!window.Redoc) {
      throw new Error('Redoc failed to attach to window')
    }

    window.Redoc.init(spec, opts, containerRef.value)
    loaded.value = true
  }
  catch (err: any) {
    error.value = err?.message ?? String(err)
  }
})
</script>

<style scoped>
.nuxt-redoc-viewer {
  height: 100%;
}

.nuxt-redoc-loading,
.nuxt-redoc-error {
  padding: 2rem;
  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  color: #666;
}

.nuxt-redoc-error {
  color: #c0392b;
}
</style>
