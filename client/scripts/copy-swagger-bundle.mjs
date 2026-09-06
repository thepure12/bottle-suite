// Vendors Swagger UI's prebuilt standalone assets into public/ so
// modules/nuxt-swagger-ui's SwaggerUIViewer can load them as plain <script>/
// <link> tags from the dashboard's own static output instead of a CDN - same
// reasoning and CJS/bundler-hostile UMD wrapper issue as
// copy-redoc-bundle.mjs, plus swagger-ui-dist ships its CSS as a separate
// file rather than inlined, so that's vendored alongside the bundle script.
// swagger-ui-standalone-preset.js is intentionally NOT vendored - it only
// provides the Topbar/StandaloneLayout, which SwaggerUIViewer.vue skips to
// avoid Swagger's own OS-driven dark mode conflicting with the dashboard's.
import { copyFileSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(fileURLToPath(import.meta.url))
const srcDir = join(root, '..', 'node_modules', 'swagger-ui-dist')
const destDir = join(root, '..', 'public', 'vendor', 'swagger')

const FILES = ['swagger-ui-bundle.js', 'swagger-ui.css']

mkdirSync(destDir, { recursive: true })
for (const file of FILES) {
  copyFileSync(join(srcDir, file), join(destDir, file))
  console.log(`Copied ${file} -> ${destDir}`)
}
