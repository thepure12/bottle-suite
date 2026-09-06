// `nuxt dev` needs to know which port the bottle-suite backend is listening
// on (it's a separate process at dev time - ssr:false + static generate
// means there's no Nuxt server proxying requests in production, so the
// dashboard talks to it directly via NUXT_PUBLIC_API_BASE). Rather than a
// `.env` file (easy to forget about and, since Nuxt auto-injects any
// NUXT_PUBLIC_* env var at build time regardless of command, a real risk of
// silently leaking a dev API base into a `nuxt generate` production build -
// see git history), the port is passed explicitly on the command line and
// wired into NUXT_PUBLIC_API_BASE only for this `nuxt dev` invocation.
import { spawn } from 'node:child_process'

const DEFAULT_PORT = 8000

const args = process.argv.slice(2)
const flagIndex = args.findIndex((a) => a === '--api-port' || a.startsWith('--api-port='))
let port = DEFAULT_PORT
if (flagIndex !== -1) {
  const flag = args[flagIndex]
  const inline = flag.split('=')[1]
  if (inline) {
    port = inline
    args.splice(flagIndex, 1)
  } else {
    port = args[flagIndex + 1]
    args.splice(flagIndex, 2)
  }
}

const child = spawn('nuxt', ['dev', ...args], {
  stdio: 'inherit',
  shell: process.platform === 'win32',
  env: {
    ...process.env,
    NUXT_PUBLIC_API_BASE: `http://localhost:${port}`,
  },
})

child.on('exit', (code) => process.exit(code ?? 0))
