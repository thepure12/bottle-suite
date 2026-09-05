// Vendors Redoc's standalone UMD bundle into public/ so modules/nuxt-redoc's
// RedocViewer can load it as a plain <script> tag from the dashboard's own
// static output instead of a CDN. The bundle can't be `import`ed/bundled
// through Vite (its UMD wrapper's CJS branch does `require("null")`, an
// artifact in the published package that only breaks in a CJS/bundler
// context) - copying the raw file and loading it via <script src> sidesteps
// that entirely.
import { copyFileSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(fileURLToPath(import.meta.url))
const src = join(root, '..', 'node_modules', 'redoc', 'bundles', 'redoc.standalone.js')
const destDir = join(root, '..', 'public', 'vendor')
const dest = join(destDir, 'redoc.standalone.js')

mkdirSync(destDir, { recursive: true })
copyFileSync(src, dest)
console.log(`Copied ${src} -> ${dest}`)
