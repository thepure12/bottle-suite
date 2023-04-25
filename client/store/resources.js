export const state = () => ({
    resources: [],
    resource: {},
    datatypes: [],
    entries: [],
})

export const mutations = {
    addResource(state, name) {
        state.resources.push(name)
    },
    setResources(state, resources) {
        state.resources = resources
    },
    setResource(state, resource) {
        state.resource = resource
    },
    setResourceAttr(state, { attrName, index, attrs }) {
        let resource = state.resource[attrName.toLowerCase()]
        if (index === -1) {
            if (attrName === "Paths") {
                attrs["index"] = resource.length
            }
            if (attrName === "Fields") {
                attrs["cid"] = resource.length
            }
            resource.push(attrs)
        }
        else
            Object.assign(resource[index], attrs)
    },
    setDatatypes(state, datatypes) {
        state.datatypes = datatypes
    },
    setEntries(state, entries) {
        state.entries = entries
    },
    setEntry(state, { entry, index }) {
        Object.assign(state.entries[index], entry)
    },
    addEntry(state, { entry }) {
        state.entries.push(entry)
    }
}

export const actions = {
    async addResource({ commit }, name) {
        await this.$axios.post("/_resources", { name: name })
            .then((res) => {
                commit("addResource", res.data)
            })
    },
    async fetchResources({ commit }) {
        let { data } = await this.$axios.get("/_resources")
        commit("setResources", data.resources)
    },
    async fetchResource({ commit }, resourceId) {
        let { data } = await this.$axios.get(`/_resources/${resourceId}`)
        commit("setResource", data)
    },
    async updateResourceAttr({ commit, state }, { attrName, index, attrs }) {
        await this.$axios.patch(`/_resources/${state.resource.name}`, {
            attr_name: attrName, value: attrs
        })
            .then(() => commit("setResourceAttr", { attrName, index, attrs }))
    },
    async fetchDatatypes({ commit }) {
        let { data } = await this.$axios.get("/_datatypes")
        commit("setDatatypes", data.datatypes)
    },
    async fetchEntries({ commit, state }) {
        let { data } = await this.$axios.get(`/${state.resource.name}`)
        commit("setEntries", data[state.resource.name])
    },
    async updateEntry({ commit, state }, { entry, index }) {
        await this.$axios.patch(`/${state.resource.name}`, entry)
            .then((res) => {
                let entry = res.data
                commit("setEntry", { entry, index })
            })
    },
    async addEntry({ commit, state }, entry) {
        await this.$axios.post(`/${state.resource.name}`, entry)
            .then((res) => {
                let entry = res.data
                commit("addEntry", { entry })
            })
    }
}