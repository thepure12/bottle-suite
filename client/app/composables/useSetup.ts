interface SetupStatus {
  configured: boolean
}

// Talks to the backend's /dashboard/setup resource (bottle_suite.dashboard.
// resources.token.DashboardToken), which lets a fresh install set its one
// admin credential the first time the dashboard is opened. Caches a
// known-configured result in a shared useState so navigating between pages
// doesn't re-check on every route once we know setup is done.
export function useSetup() {
  const knownConfigured = useState<boolean | null>('setup:configured', () => null)

  async function checkSetupNeeded(): Promise<boolean> {
    if (knownConfigured.value) return false
    const api = useApi()
    const status = await api<SetupStatus>('/dashboard/setup')
    knownConfigured.value = status.configured
    return !status.configured
  }

  async function submitSetup(username: string, password: string) {
    const api = useApi()
    await api('/dashboard/setup', {
      method: 'POST',
      body: { username, password },
    })
    knownConfigured.value = true
  }

  return { checkSetupNeeded, submitSetup }
}
