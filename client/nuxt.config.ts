import { fileURLToPath } from 'node:url'

// This dashboard is generated statically (`nuxt generate`) and served
// directly by the Python Bottle backend (see setupDashboard/DIST in
// src/bottle_suite/bottle_suite.py) - there is no Nitro/Node server running
// in production, so `ssr` must stay false and the output must land in
// src/bottle_suite/dashboard/dist with a flat _nuxt/ asset folder.
export default defineNuxtConfig({
  ssr: false,

  modules: ['@nuxt/ui', './modules/nuxt-redoc/module.ts', './modules/nuxt-swagger-ui/module.ts'],

  // api-docs.vue / api-explorer.vue drive <RedocViewer>/<SwaggerUIViewer>
  // directly (loading/disabled-state detection lives there already), so skip
  // each module's own auto-added page.
  redoc: {
    route: false,
  },
  swaggerUi: {
    route: false,
  },

  // Every template in this app references subdirectory components by their
  // bare filename (e.g. <ResourceDataTable>, <PageHeader>) rather than
  // Nuxt's default directory-prefixed name (e.g. ResourcesResourceDataTable,
  // BasePageHeader) - disable prefixing so those resolve as written.
  components: [{ path: '~/components', pathPrefix: false }],

  css: ['~/assets/css/main.css'],

  // Defaults to dark (matches the old forced-dark Vuetify look) but the
  // navbar now exposes a toggle (see app/layouts/default.vue) rather than
  // hard-locking colorMode as the previous config did.
  colorMode: {
    preference: 'dark',
    fallback: 'dark',
  },

  app: {
    baseURL: '/dashboard/',
    head: {
      title: 'Bottle Suite',
      // No hardcoded class here - @nuxtjs/color-mode (via colorMode below)
      // owns the <html> class and toggles it at runtime; a static 'dark'
      // here would linger alongside 'light' once toggled and always win
      // the cascade (both classes present, .dark declared later in CSS).
      htmlAttrs: { lang: 'en' },
      meta: [
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'format-detection', content: 'telephone=no' },
      ],
      // No manual Google Fonts <link> here: @nuxt/ui auto-registers
      // @nuxt/fonts and self-hosts whatever --font-sans/--font-mono
      // main.css declares (see the woff2 files it downloads into
      // dist/_fonts/ at `nuxt generate` time) - better than a CDN <link>
      // since it has no external runtime dependency.
      link: [
        // Two `rel: 'icon'` links, differentiated by `type`, is the standard
        // dual-favicon pattern - browsers without SVG favicon support fall
        // back to the .ico automatically ('alternate icon' isn't a valid
        // rel value in the HTML spec's favicon algorithm despite some blog
        // posts using it).
        { rel: 'icon', type: 'image/svg+xml', href: '/dashboard/favicon.svg' },
        { rel: 'icon', type: 'image/x-icon', href: '/dashboard/favicon.ico' },
      ],
    },
  },

  runtimeConfig: {
    public: {
      // Baked in at `nuxt generate` time (no server left at request time to
      // resolve this dynamically under ssr:false). '' = same-origin, correct
      // for production where Bottle serves both the API and the dashboard.
      // Overridden via client/.env's NUXT_PUBLIC_API_BASE for `nuxt dev`.
      apiBase: '',
    },
  },

  nitro: {
    output: {
      publicDir: fileURLToPath(new URL('../src/bottle_suite/dashboard/dist', import.meta.url)),
    },
  },

  icon: {
    clientBundle: {
      scan: true,
      sizeLimitKb: 512,
    },
  },

  compatibilityDate: '2026-01-01',
})
