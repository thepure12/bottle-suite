// Shared $fetch instance, replaces @nuxtjs/axios. Attaches the JWT bearer
// token to every request and logs out on 401 (expired/invalid token) only -
// NOT on 400, since PUT /bottle_suite_cfg legitimately returns 400 for a bad
// TOML save and that must not force a logout.
export function useApi() {
  const config = useRuntimeConfig()

  return $fetch.create({
    baseURL: config.public.apiBase,
    onRequest({ options }) {
      const token = useCookie<string | null>('bottle_suite_token').value
      if (token) {
        const headers = new Headers(options.headers)
        headers.set('Authorization', `Bearer ${token}`)
        options.headers = headers
      }
    },
    onResponseError({ response }) {
      if (response.status === 401) {
        const { logout } = useAuth()
        logout()
      }
    },
  })
}
