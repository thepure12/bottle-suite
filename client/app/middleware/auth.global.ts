// Replaces the virtual "auth" middleware from @nuxtjs/auth-next, which the
// old app only applied to pages/resources/index.vue. This runs globally so
// every page is guarded except /login and /setup.
//
// /setup is the first-run "create the admin account" screen (see
// useSetup.ts) - it must stay reachable with no token, but only until an
// admin credential actually exists, after which it redirects to /login.
export default defineNuxtRouteMiddleware(async (to) => {
  const { isLoggedIn } = useAuth()
  const { checkSetupNeeded } = useSetup()

  if (to.path === '/setup') {
    if (!(await checkSetupNeeded())) return navigateTo('/login')
    return
  }

  if (to.path === '/login') {
    if (await checkSetupNeeded()) return navigateTo('/setup')
    return
  }

  if (!isLoggedIn.value) {
    if (await checkSetupNeeded()) return navigateTo('/setup')
    return navigateTo('/login')
  }
})
