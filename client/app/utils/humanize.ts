// SQLite pragma / backend-internal keys that don't humanize well generically
// (e.g. naive Title Case would give "Notnull" or bare "Key"/"Default").
const KNOWN_LABELS: Record<string, string> = {
  notnull: 'Not null',
  default: 'Default value',
  key: 'Primary key',
  jwt_key: 'JWT key',
}

export function humanizeKey(key: string): string {
  if (KNOWN_LABELS[key]) return KNOWN_LABELS[key]

  return key
    .replace(/[_-]+/g, ' ')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .split(' ')
    .filter(Boolean)
    .map((word, i) => (i === 0 ? word.charAt(0).toUpperCase() + word.slice(1) : word.toLowerCase()))
    .join(' ')
}
