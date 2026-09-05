import { defineNuxtModule, createResolver, addComponent, extendPages } from '@nuxt/kit'

export interface ModuleOptions {
  /**
   * URL or path to your OpenAPI/Swagger spec.
   * Can be a public asset path (e.g. '/openapi.json') or a remote URL.
   */
  specUrl: string
  /**
   * Route path where the auto-generated explorer page will be mounted.
   * Set to false to skip adding a page (use the <SwaggerUIViewer> component yourself instead).
   */
  route: string | false
  /**
   * Options merged into the SwaggerUIBundle({ ... }) config object.
   * See https://github.com/swagger-api/swagger-ui/blob/master/docs/usage/configuration.md
   */
  swaggerOptions: Record<string, any>
}

export default defineNuxtModule<ModuleOptions>({
  meta: {
    name: 'nuxt-swagger-ui',
    configKey: 'swaggerUi',
    compatibility: {
      nuxt: '>=3.9.0',
    },
  },
  defaults: {
    specUrl: '/openapi.json',
    route: '/api-explorer',
    swaggerOptions: {},
  },
  setup(options, nuxt) {
    const resolver = createResolver(import.meta.url)

    // Expose options to the client at runtime
    nuxt.options.runtimeConfig.public.swaggerUi = {
      specUrl: options.specUrl,
      swaggerOptions: options.swaggerOptions,
    }

    // Register <SwaggerUIViewer /> as a global, client-only component
    addComponent({
      name: 'SwaggerUIViewer',
      filePath: resolver.resolve('./runtime/components/SwaggerUIViewer.vue'),
      mode: 'client',
    })

    // Optionally add a ready-made /api-explorer page
    if (options.route) {
      extendPages((pages) => {
        pages.push({
          name: 'nuxt-swagger-ui-explorer',
          path: options.route as string,
          file: resolver.resolve('./runtime/pages/explorer.vue'),
        })
      })
    }
  },
})
