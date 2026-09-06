export interface ResourceSummary {
  name: string
  id: string
}

export interface ResourcePath {
  path: string
  index: number
}

export interface ResourceRole {
  method: string
  roles: boolean | string[]
}

export interface ResourceField {
  name: string
  type: string
  notnull: boolean
  default: string | null
  key: number
  [key: string]: unknown
}

export interface ResourceDetail {
  name: string
  fields: ResourceField[]
  paths: ResourcePath[]
  roles: ResourceRole[]
}

// Replaces store/resources.js (Vuex). Backed by useState so every component
// that calls this composable shares the same reactive instance.
export function useResourcesStore() {
  const resources = useState<ResourceSummary[]>('resources:list', () => [])
  const resource = useState<ResourceDetail | null>('resources:current', () => null)
  const datatypes = useState<string[]>('resources:datatypes', () => [])
  const entries = useState<Record<string, unknown>[]>('resources:entries', () => [])

  async function fetchResources() {
    const api = useApi()
    const { resources: data } = await api<{ resources: ResourceSummary[] }>('/_resources')
    resources.value = data
  }

  async function addResource(name: string) {
    const api = useApi()
    const created = await api<ResourceSummary>('/_resources', {
      method: 'POST',
      body: { name },
    })
    resources.value.push(created)
    return created
  }

  async function fetchResource(id: string) {
    const api = useApi()
    resource.value = await api<ResourceDetail>(`/_resources/${id}`)
  }

  // attr_name/value shape matches AllResources.patch on the backend exactly
  // (resources.py): "roles" -> {method, roles: "true"|"false"|"role,role"},
  // "paths" -> {index, path}, "fields" -> full field-attrs dict for
  // alterDBTable. The backend returns no body on success, so re-fetch the
  // resource afterwards rather than trying to replicate its array-mutation
  // semantics (index-or-append for paths, rename-or-add for fields) locally.
  async function updateResourceAttr(attrName: 'roles' | 'paths' | 'fields', value: Record<string, unknown>) {
    if (!resource.value) return
    const name = resource.value.name
    const api = useApi()
    await api(`/_resources/${name}`, {
      method: 'PATCH',
      body: { attr_name: attrName, value },
    })
    await retryAfterReload(() => fetchResource(name))
  }

  // Removes one path/field entry from the resource without deleting the
  // whole resource -- attr_name mirrors updateResourceAttr's dispatch shape.
  async function removeResourceAttr(attrName: 'remove_path', index: number) {
    if (!resource.value) return
    const name = resource.value.name
    const api = useApi()
    await api(`/_resources/${name}`, {
      method: 'PATCH',
      body: { attr_name: attrName, value: { index } },
    })
    await retryAfterReload(() => fetchResource(name))
  }

  async function deleteResource(id: string) {
    const api = useApi()
    await api(`/_resources/${id}`, { method: 'DELETE' })
    resources.value = resources.value.filter(r => r.id !== id)
  }

  async function fetchDatatypes() {
    const api = useApi()
    const { datatypes: data } = await api<{ datatypes: string[] }>('/_datatypes')
    datatypes.value = data
  }

  async function fetchEntries() {
    if (!resource.value) return
    const api = useApi()
    const data = await api<Record<string, Record<string, unknown>[]>>(`/${resource.value.name}`)
    entries.value = data[resource.value.name] ?? []
  }

  async function addEntry(entry: Record<string, unknown>) {
    if (!resource.value) return
    const api = useApi()
    const created = await api<Record<string, unknown>>(`/${resource.value.name}`, {
      method: 'POST',
      body: entry,
    })
    entries.value.push(created)
  }

  async function updateEntry(entry: Record<string, unknown>, index: number) {
    if (!resource.value) return
    const pk = resource.value.fields.find(f => f.key === 1)?.name
    if (!pk) return
    const { [pk]: _pk, ...body } = entry
    const api = useApi()
    const updated = await api<Record<string, unknown>>(`/${resource.value.name}/${entry[pk]}`, {
      method: 'PATCH',
      body,
    })
    entries.value[index] = updated
  }

  async function deleteEntry(index: number) {
    if (!resource.value) return
    const pk = resource.value.fields.find(f => f.key === 1)?.name
    const entry = entries.value[index]
    if (!pk || !entry) return
    const api = useApi()
    await api(`/${resource.value.name}/${entry[pk]}`, { method: 'DELETE' })
    entries.value.splice(index, 1)
  }

  return {
    resources,
    resource,
    datatypes,
    entries,
    fetchResources,
    addResource,
    deleteResource,
    fetchResource,
    updateResourceAttr,
    removeResourceAttr,
    fetchDatatypes,
    fetchEntries,
    addEntry,
    updateEntry,
    deleteEntry,
  }
}
