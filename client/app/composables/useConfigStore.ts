import { parse, stringify } from 'smol-toml'

export interface KeyValueRow {
  key: string
  value: string
}

export interface FieldDef {
  key: string
  label: string
  type?: 'text' | 'password' | 'number' | 'boolean'
  default?: string
}

export interface PluginSection {
  enabled: boolean
  known: Record<string, string>
  extra: KeyValueRow[]
}

// The backend (bottle_suite.py setupJwt/setupSql/setupSqlite) accepts each
// of these sections as bool | string-shorthand | dict. This adapter
// normalizes any of those shapes into a flat {enabled, known, extra} form
// the UI can render, and serializes back preserving the shorthand whenever
// only the section's primary field is set (matching the backend's own
// string-shorthand -> {primaryKey: value} expansion, so round-tripping a
// config that never uses "extra" kwargs stays terse).
export function sectionFromToml(raw: unknown, knownKeys: string[], primaryKey: string): PluginSection {
  if (raw === undefined || raw === false) {
    return { enabled: false, known: Object.fromEntries(knownKeys.map(k => [k, ''])), extra: [] }
  }
  if (raw === true) {
    return { enabled: true, known: Object.fromEntries(knownKeys.map(k => [k, ''])), extra: [] }
  }
  if (typeof raw === 'string') {
    const known = Object.fromEntries(knownKeys.map(k => [k, '']))
    known[primaryKey] = raw
    return { enabled: true, known, extra: [] }
  }
  if (typeof raw === 'object' && raw !== null) {
    const known: Record<string, string> = Object.fromEntries(knownKeys.map(k => [k, '']))
    const extra: KeyValueRow[] = []
    for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
      if (knownKeys.includes(key)) {
        known[key] = value == null ? '' : String(value)
      } else {
        extra.push({ key, value: typeof value === 'string' ? value : JSON.stringify(value) })
      }
    }
    return { enabled: true, known, extra }
  }
  return { enabled: false, known: Object.fromEntries(knownKeys.map(k => [k, ''])), extra: [] }
}

function coerceValue(value: string): unknown {
  try {
    return JSON.parse(value)
  } catch {
    return value
  }
}

export function sectionToToml(section: PluginSection, primaryKey: string): unknown {
  if (!section.enabled) return false

  const setKnown = Object.entries(section.known).filter(([, v]) => v !== '')
  if (section.extra.length === 0 && setKnown.length === 0) return true
  if (section.extra.length === 0 && setKnown.length === 1) {
    const [key, value] = setKnown[0] ?? []
    if (key === primaryKey) return value
  }

  const table: Record<string, unknown> = {}
  for (const [key, value] of setKnown) table[key] = coerceValue(value)
  for (const row of section.extra) {
    if (row.key) table[row.key] = coerceValue(row.value)
  }
  return table
}

// Replaces store/index.js (Vuex). GET/PUT /bottle_suite_cfg round-trips the
// *entire* config as a raw TOML string - there is no partial-update API, so
// the whole parsed object is kept here and re-serialized on save.
export function useConfigStore() {
  const parsed = useState<Record<string, unknown>>('config:parsed', () => ({}))
  const loading = useState<boolean>('config:loading', () => false)

  async function fetchConfig() {
    loading.value = true
    try {
      const api = useApi()
      const raw = await api<string>('/bottle_suite_cfg')
      parsed.value = parse(raw)
    } finally {
      loading.value = false
    }
  }

  async function saveConfig() {
    const api = useApi()
    const tomlString = stringify(parsed.value)
    await api('/bottle_suite_cfg', { method: 'PUT', body: { config: tomlString } })
  }

  return { parsed, loading, fetchConfig, saveConfig }
}
