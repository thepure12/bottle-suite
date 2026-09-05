# nuxt-redoc

Drop-in [Redoc](https://github.com/Redocly/redoc) (OpenAPI documentation) integration for **Nuxt 4**.

Loads the official Redoc standalone bundle client-side (no SSR issues) and gives you:

- A ready-made `/api-docs` page (configurable route)
- A `<RedocViewer />` component you can drop anywhere yourself
- Config via `nuxt.config.ts` or per-component props

## Install (local module)

1. Copy this `nuxt-redoc/` folder into your project, e.g. at `modules/nuxt-redoc/`.
2. Register it in `nuxt.config.ts`:

```ts
export default defineNuxtConfig({
  modules: ['./modules/nuxt-redoc/module.ts'],

  redoc: {
    specUrl: '/openapi.yaml',   // path in /public, or a full URL
    route: '/api-docs',          // set to false to skip auto page
    redocOptions: {
      hideDownloadButton: false,
      theme: {
        colors: { primary: { main: '#7c3aed' } },
      },
    },
  },
})
```

3. Put your OpenAPI spec file in `public/openapi.yaml` (or `.json`), or point `specUrl` at a remote URL.
4. Vendor the Redoc standalone bundle into `public/vendor/redoc.standalone.js` (this project does it via a `redoc` devDependency + `scripts/copy-redoc-bundle.mjs` run from `postinstall` — see that file's comment for why it must be copied as a static asset rather than `import`ed).
5. Run `nuxt dev` and visit `/api-docs`.

## Using the component directly

If you set `route: false`, or just want more control over the page/layout, use the
auto-imported component yourself:

```vue
<template>
  <ClientOnly>
    <RedocViewer
      spec-url="/openapi.yaml"
      :redoc-options="{ hideDownloadButton: true }"
    />
  </ClientOnly>
</template>
```

`RedocViewer` must be wrapped in `<ClientOnly>` (or used on a client-only route) since Redoc
manipulates the DOM directly and isn't SSR-safe.

## Options

| Option         | Type                    | Default             | Description                                      |
|----------------|-------------------------|----------------------|---------------------------------------------------|
| `specUrl`      | `string`                | `/openapi.yaml`      | Path or URL to your OpenAPI/Swagger spec           |
| `route`        | `string \| false`       | `/api-docs`          | Route for the auto-added docs page                |
| `redocOptions` | `Record<string, any>`   | `{}`                 | Passed straight to `Redoc.init(spec, options, el)` — see [Redoc options](https://github.com/Redocly/redoc#redoc-options-object) |

## Notes

- `RedocViewer` loads Redoc's official standalone JS bundle via a plain `<script src="/vendor/redoc.standalone.js">`
  tag (no SSR issues, no React/ReactDOM/`redoc` runtime dependency in your own bundle). It expects that file to
  already exist under `public/vendor/` — vendor it from the `redoc` npm package rather than a CDN, so the page
  works fully offline and stays reproducible via your lockfile (this project's `scripts/copy-redoc-bundle.mjs`
  does this on `postinstall`). Note the bundle can't be `import`ed/bundled through Vite itself — its UMD wrapper's
  CJS branch throws (`require("null")`, an artifact of how it's published) — it only works loaded as a plain script.
- Works with Nuxt 4's default `app/` source directory layout; nothing here assumes `srcDir`.
