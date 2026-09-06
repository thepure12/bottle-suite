// Shared by useResourcesStore/usePythonResourcesStore: PATCHes that touch
// reload.py restart the reloader=True dev process (see CLAUDE.md's "Live
// reload" note) -- an immediate refetch can land in the brief window
// between the old process exiting and the new one binding the port, so
// retry a few times rather than surfacing a spurious save failure for an
// edit that already persisted to bottle_suite.toml.
export async function retryAfterReload<T>(fn: () => Promise<T>, attempts = 5, delayMs = 300): Promise<T> {
  let lastError: unknown
  for (let attempt = 0; attempt < attempts; attempt++) {
    try {
      return await fn()
    } catch (e) {
      lastError = e
      if (attempt < attempts - 1) await new Promise(resolve => setTimeout(resolve, delayMs))
    }
  }
  throw lastError
}
