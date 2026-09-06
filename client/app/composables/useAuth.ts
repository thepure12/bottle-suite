interface CurrentUser {
  user: string
}

// Replaces @nuxtjs/auth-next's "local" strategy (unmaintained on Nuxt 3/4).
// Token lives in a reactive cookie rather than @nuxtjs/auth-next's storage -
// there is no server at request time (ssr:false + static generate) so this
// is purely a client-accessible, reactive key/value store.
export function useAuth() {
  const token = useCookie<string | null>('bottle_suite_token', {
    default: () => null,
    sameSite: 'lax',
  })
  const user = useState<CurrentUser | null>('auth:user', () => null)
  const isLoggedIn = computed(() => !!token.value)

  async function login(username: string, password: string) {
    const api = useApi()
    const res = await api<{ token: string }>('/dashboard/token', {
      method: 'POST',
      body: { username, password },
    })
    token.value = res.token
    await fetchUser()
  }

  async function fetchUser() {
    const api = useApi()
    user.value = await api<CurrentUser>('/users/current')
  }

  function logout() {
    token.value = null
    user.value = null
    navigateTo('/login')
  }

  return { token, user, isLoggedIn, login, logout, fetchUser }
}
