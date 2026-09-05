import { defineNuxtModule, createResolver, addComponent, extendPages } from '@nuxt/kit'

export interface ModuleOptions {
  /**
   * URL or path to your OpenAPI/Swagger spec.
   * Can be a public asset path (e.g. '/openapi.yaml') or a remote URL.
   */
  specUrl: string
  /**
   * Route path where the auto-generated docs page will be mounted.
   * Set to false to skip adding a page (use the <RedocViewer> component yourself instead).
   */
  route: string | false
  /**
   * Options passed straight through to Redoc.init(spec, options, el).
   * See https://github.com/Redocly/redoc#redoc-options-object
   */
  redocOptions: Record<string, any>
}

export default defineNuxtModule<ModuleOptions>({
  meta: {
    name: 'nuxt-redoc',
    configKey: 'redoc',
    compatibility: {
      nuxt: '>=3.9.0',
    },
  },
  defaults: {
    specUrl: '/openapi.yaml',
    route: '/api-docs',
    redocOptions: {},
  },
  setup(options, nuxt) {
    const resolver = createResolver(import.meta.url)

    // Expose options to the client at runtime
    nuxt.options.runtimeConfig.public.redoc = {
      specUrl: options.specUrl,
      redocOptions: options.redocOptions,
    }

    // Register <RedocViewer /> as a global, client-only component
    addComponent({
      name: 'RedocViewer',
      filePath: resolver.resolve('./runtime/components/RedocViewer.vue'),
      mode: 'client',
    })

    // Optionally add a ready-made /api-docs page
    if (options.route) {
      extendPages((pages) => {
        pages.push({
          name: 'nuxt-redoc-docs',
          path: options.route as string,
          file: resolver.resolve('./runtime/pages/docs.vue'),
        })
      })
    }
  },
})
