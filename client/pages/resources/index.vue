<template>
    <v-card :loading="loading">
        <v-toolbar color="light-blue" dark>
            <v-toolbar-title>Database Resources</v-toolbar-title>
            <v-spacer></v-spacer>
            <v-btn icon @click="dialogAdd = true">
                <v-icon color="white">mdi-plus-circle</v-icon>
            </v-btn>
        </v-toolbar>
        <v-dialog v-model="dialogAdd" persistent transition="dialog-top-transition" max-width="500">
            <v-card>
                <v-card-title>
                    <span class="text-h5">Add Resource</span>
                </v-card-title>
                <v-card-text>
                    <v-text-field v-for="(v, k, i) in newResource" :key="k" :label="k" v-model="newResource[k]" placeholder="new_resource">
                    </v-text-field>
                </v-card-text>
                <v-card-actions>
                    <v-spacer></v-spacer>
                    <v-btn color="blue-darken-1" variant="text" @click="closeAdd">
                        Cancel
                    </v-btn>
                    <v-btn color="blue-darken-1" variant="text" @click="save">
                        Save
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
        <v-list>
            <template v-for="(resource, i) in resources">
                <v-list-item :key="resource.name" :to="`/resources/${resource.id}`">
                    <v-list-item-content>
                        <v-list-item-title>
                            {{ resource.name }}
                        </v-list-item-title>
                    </v-list-item-content>
                    <v-list-item-action>
                        <v-btn icon :to="`/resources/${resource.id}`">
                            <v-icon color="blue lighten-1">mdi-eye</v-icon>
                        </v-btn>
                    </v-list-item-action>
                </v-list-item>
                <v-divider v-if="i < resources.length - 1" :key="i"></v-divider>
            </template>
        </v-list>
    </v-card>
</template>
<script>
import { mapState } from "vuex";
export default {
    name: "Resources",
    middleware: "auth",
    data() {
        return {
            loading: true,
            dialogAdd: false,
            newResource: { name: "" }
        }
    },
    computed: {
        ...mapState("resources", ["resources"])
    },
    methods: {
        closeAdd() {
            this.dialogAdd = false
            this.newResource = { name: "" }
        },
        save() {
            this.loading = true
            this.$store.dispatch("resources/addResource", this.newResource.name)
                .then(() => {
                    this.loading = false
                    this.closeAdd()
                })
        }
    },
    mounted() {
        this.$store.dispatch("resources/fetchResources")
            .then(() => this.loading = false)
    }
}
</script>