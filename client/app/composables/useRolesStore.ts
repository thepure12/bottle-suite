import type { ResourceRole } from '~/composables/useResourcesStore'

export interface RoleResourceEntry {
  name: string
  kind: 'db' | 'python'
  roles: ResourceRole[]
}

export interface RolesBulkUpdate {
  resource: string
  methods: string[]
  roles: boolean | string[]
}

// Backs the cross-resource "Roles" page (GET/PATCH /_roles) -- a single
// combined view of every DB + Python resource's roles, and a single bulk
// PATCH that mutates all of them with one saveConfig()/reloadServer() pass
// server-side, instead of one reload per resource.
export function useRolesStore() {
  const resources = useState<RoleResourceEntry[]>('roles:all', () => [])

  async function fetchAllRoles() {
    const api = useApi()
    const { resources: data } = await api<{ resources: RoleResourceEntry[] }>('/_roles')
    resources.value = data
  }

  async function updateRolesBulk(updates: RolesBulkUpdate[]) {
    const api = useApi()
    await api('/_roles', { method: 'PATCH', body: { updates } })
    await retryAfterReload(fetchAllRoles)
  }

  return { resources, fetchAllRoles, updateRolesBulk }
}
