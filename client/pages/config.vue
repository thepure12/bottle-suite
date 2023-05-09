<template>
    <v-card>
        <v-toolbar color="light-blue" dark>
            <v-toolbar-title>Bottle Suite Config</v-toolbar-title>
            <v-spacer></v-spacer>
            <v-btn icon @click="updateConfig">
                <v-icon color="white">mdi-content-save</v-icon>
            </v-btn>
        </v-toolbar>
        <div class="d-flex">
            <div class="line-numbers">
                <v-textarea :value="lineNumbers" class="pa-5 pr-0 text-right" disabled auto-grow></v-textarea>
            </div>
            <div class="config">
                <v-textarea v-model="config" class="pa-5" auto-grow></v-textarea>
            </div>
        </div>
    </v-card>
</template>
<script>
import { mapState } from "vuex";
export default {
    data: () => {
        return {

        }
    },
    computed: {
        config: {
            get() {
                return this.$store.state.config
            },
            set(newValue) {
                this.$store.commit("setConfig", newValue)
            }
        },
        lineNumbers() {
            let lineNumbers = ""
            let lines = this.config.match(/\n/g) || []
            for (let [i, e] of lines.entries()) {
                lineNumbers += `${i + 1}${e}`
            }
            return lineNumbers
        }
    },
    methods: {
        updateConfig(evt) {
            this.$store.dispatch("updateConfig", this.config)
        }
    },
    mounted() {
        this.$store.dispatch("fetchConfig")
    }
}
</script>
<style>
.text-right textarea {
    text-align: right !important;
}

.line-numbers {
    max-width: 50px;
}

.config textarea {
    white-space: nowrap;
}

.config {
    width: 100%;
}
</style>