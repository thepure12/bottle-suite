export const state = () => ({
    config: ""
})

export const mutations = {
    setConfig(state, config) {
        state.config = config
    }
}

export const actions = {
    async fetchConfig({ commit }) {
        await this.$axios.get("/bottle_suite_cfg")
            .then(res => { commit("setConfig", res.data) })
    },
    async updateConfig({ commit }, config) {
        await this.$axios.put("/bottle_suite_cfg", { "config": config })
            .then(res => { })
            .catch(error => {
                $nuxt.vtoast.show({
                    message: error.response.data.message,
                    color: "red",
                    icon: "mdi-close-octagon"
                })
            })
    }
}