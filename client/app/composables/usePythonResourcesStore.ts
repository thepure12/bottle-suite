import type { ResourcePath, ResourceRole } from './useResourcesStore'

export interface PythonResourceSummary {
  name: string
}

export interface PythonResourceDetail {
  name: string
  paths: ResourcePath[]
  roles: ResourceRole[]
}

// Backed by useState so every component sharing this composable sees the
// same list/current resource.
export function usePythonResourcesStore() {
  const resources = useState<PythonResourceSummary[]>('pythonResources:list', () => [])
  const resource = useState<PythonResourceDetail | null>('pythonResources:current', () => null)

  async function fetchPythonResources() {
    const api = useApi()
    const { resources: data } = await api<{ resources: PythonResourceSummary[] }>('/_python_resources')
    resources.value = data
  }

  async function createPythonResource(name: string) {
    const api = useApi()
    const created = await api<PythonResourceSummary>('/_python_resources', {
      method: 'POST',
      body: { name },
    })
    resources.value.push(created)
    return created
  }

  async function fetchPythonResource(name: string) {
    const api = useApi()
    resource.value = await api<PythonResourceDetail>(`/_python_resources/${name}`)
  }

  // attr_name/value shape matches PythonResources.patch on the backend
  // (resources.py): "roles" -> {method, roles: "true"|"false"|"role,role"},
  // "paths" -> {index, path}. The backend returns no body on success, so
  // re-fetch the resource afterwards rather than replicating its
  // array-mutation semantics locally.
  async function updateResourceAttr(attrName: 'roles' | 'paths', value: Record<string, unknown>) {
    if (!resource.value) return
    const name = resource.value.name
    const api = useApi()
    await api(`/_python_resources/${name}`, {
      method: 'PATCH',
      body: { attr_name: attrName, value },
    })
    await retryAfterReload(() => fetchPythonResource(name))
  }

  async function removeResourceAttr(attrName: 'remove_path', index: number) {
    if (!resource.value) return
    const name = resource.value.name
    const api = useApi()
    await api(`/_python_resources/${name}`, {
      method: 'PATCH',
      body: { attr_name: attrName, value: { index } },
    })
    await retryAfterReload(() => fetchPythonResource(name))
  }

  async function deletePythonResource(name: string) {
    const api = useApi()
    await api(`/_python_resources/${name}`, { method: 'DELETE' })
    resources.value = resources.value.filter(r => r.name !== name)
  }

  return {
    resources,
    resource,
    fetchPythonResources,
    createPythonResource,
    deletePythonResource,
    fetchPythonResource,
    updateResourceAttr,
    removeResourceAttr,
  }
}
