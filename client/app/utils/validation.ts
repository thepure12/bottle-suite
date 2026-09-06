// Mirrors src/bottle_suite/resource_scaffold.py's NAME_RE exactly. UX-only:
// the backend re-validates (after .strip().lower()) and remains the source
// of truth.
export const RESOURCE_NAME_RE = /^[a-z_][a-z0-9_]*$/

export function isValidResourceName(name: string): boolean {
  return RESOURCE_NAME_RE.test(name.trim().toLowerCase())
}
