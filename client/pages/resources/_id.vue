<template>
    <v-card :loading="loading" class="pb-1">
        <v-toolbar color="light-blue" class="text-h5" dark>
            <v-btn icon to="/resources">
                <v-icon color="white">mdi-arrow-left-circle</v-icon>
            </v-btn>
            <span>{{ loading ? "" : resource.name }}</span>
        </v-toolbar>
        <v-card>
            <v-toolbar>
                <v-tabs v-model="tab" background-color="accent-4" grow center-active dark>
                    <v-tab v-for="tab in tabs" :key="tab" :to="`#${tab}`">{{ tab }}</v-tab>
                </v-tabs>
            </v-toolbar>
            <v-dialog v-model="dialogEdit" persistent transition="dialog-top-transition" max-width="500">
                <v-card>
                    <v-card-title>
                        <span class="text-h5">{{ formTitle }}</span>
                    </v-card-title>
                    <v-card-text>
                        <template v-for="key in editedItemKeys">
                            <v-select v-if="key === 'type'" :key="key" :label="key" :disabled="doDisable(key)"
                                v-model="editedItem[key]" :items="datatypes"></v-select>
                            <v-switch v-else-if="key === 'notnull'" :key="key" :disabled="doDisable(key)"
                                v-model="editedItem[key]" :true-value="1" :false-value="0" class="v-input--reverse"
                                :label="key"></v-switch>
                            <v-text-field v-else :key="key" :label="key" :disabled="doDisable(key)"
                                v-model="editedItem[key]">
                            </v-text-field>
                        </template>
                    </v-card-text>
                    <v-card-actions>
                        <v-spacer></v-spacer>
                        <v-btn color="blue-darken-1" variant="text" @click="closeEdit">
                            Cancel
                        </v-btn>
                        <v-btn color="blue-darken-1" variant="text" @click="save">
                            Save
                        </v-btn>
                    </v-card-actions>
                </v-card>
            </v-dialog>
            <v-tabs-items v-model="tab">
                <v-tab-item v-for="tab in tabs" :key="tab" :value="tab">
                    <v-card class="ma-3" color="white" outlined>
                        <v-toolbar color="light-blue">
                            <v-toolbar-title>{{ tab }}</v-toolbar-title>
                            <v-spacer></v-spacer>
                            <v-btn v-if="tab !== 'Roles'" icon @click="editItem(false)">
                                <v-icon color="white">mdi-plus-circle</v-icon>
                            </v-btn>
                        </v-toolbar>
                        <v-alert v-model="dialogDelete" class="mx-0 my-1" color="green" icon="mdi-progress-question"
                            border="left" transition="scale-transition" dismissible>Delete Coming Soon!</v-alert>
                        <v-data-table :items="items" :headers="headers" :itemsPerPage="20" class="elevation-1"
                            :footer-props="{ 'items-per-page-options': [20, 50, 100, -1] }">
                            <template #[`item.actions`]="{ item }">
                                <v-container>
                                    <v-row>
                                        <v-spacer></v-spacer>
                                        <v-icon small class="mr-2" @click="editItem(item)">
                                            mdi-pencil
                                        </v-icon>
                                        <v-icon small @click="deleteItem(item)">
                                            mdi-delete
                                        </v-icon>
                                    </v-row>
                                </v-container>
                            </template>
                            <template #no-data>
                                <v-container>
                                    <h3>No data available. Try refreshing. Server maybe reloading.</h3>
                                    <v-btn icon x-large @click="loadResource" color="light-blue">
                                        <v-icon>mdi-refresh</v-icon>
                                    </v-btn>
                                </v-container>
                            </template>
                        </v-data-table>
                    </v-card>
                </v-tab-item>
            </v-tabs-items>
        </v-card>

    </v-card>
</template>
<script>
import { mapState } from "vuex";
export default {
    data: () => ({
        loading: true,
        tab: "Fields",
        tabs: ["Fields", "Paths", "Roles", "Entries"],
        editedItem: {},
        editedIndex: -1,
        dialogEdit: false,
        dialogDelete: false,
        formTitle: "Edit"
    }),
    computed: {
        ...mapState("resources", ["resource", "datatypes", "entries"]),
        resourceId() {
            return this.$route.params.id
        },
        items() {
            if (this.tab === "Entries")
                return this.entries
            else
                return this.resource[this.tab.toLowerCase()]
        },
        editedItemKeys() {
            return Object.keys(this.editedItem).filter(key => key !== "index")
        },
        headers() {
            let headers
            if (this.items && this.items.length) {
                headers = Object.keys(this.items[0])
                    .map(k => ({ "text": k, "value": k }))
                headers.push({ text: '', value: 'actions', sortable: false })
                return headers
            }
            else if (this.tab === "Entries") {
                let fields = this.resource["fields"]
                if (fields && fields.length) {
                    headers = fields
                        .map(k => ({ "text": k.name, "value": k.name }))
                    headers.push({ text: '', value: 'actions', sortable: false })
                }
                return headers
            }
        },
        defaultItem() {
            let item = {}
            for (let h of this.headers)
                if (h.value !== "actions")
                    item[h.value] = ""
            return item
        }
    },
    methods: {
        loadResource() {
            this.$store.dispatch("resources/fetchResource", this.resourceId)
                .then(() => {
                    this.loading = false
                    this.$store.dispatch("resources/fetchDatatypes")
                    this.$store.dispatch("resources/fetchEntries")
                })
        },
        doDisable(key) {
            let a = key.match(/^(cid|method)$/) != null
            let b = key.match(/^(type|notnull|dflt_value|pk)$/) != null && this.editedItem["cid"] !== ""
            let c = this.tab === "Entries" && this.resource.fields.find(e => e.pk = 1).name === key
            return (a || b || c)
        },
        editItem(item) {
            if (item) {
                this.editedItem = Object.assign({}, item)
                this.editedIndex = this.items.indexOf(item)
            }
            else
                this.editedItem = Object.assign({}, this.defaultItem)
            this.dialogEdit = true
            console.log(this.editedIndex);
        },
        closeEdit() {
            this.dialogEdit = false
            this.$nextTick(() => {
                this.editedItem = Object.assign({}, this.defaultItem)
                this.editedIndex = -1
            })
        },
        save() {
            this.loading = true
            if (this.tab === "Entries")
                if (this.editedIndex === -1)
                    this.$store.dispatch("resources/addEntry", this.editedItem)
                        .then(() => {
                            this.loading = false
                            this.closeEdit()
                        })
                else
                    this.$store.dispatch("resources/updateEntry", {
                        entry: this.editedItem,
                        index: this.editedIndex
                    })
                        .then(() => {
                            this.loading = false
                            this.closeEdit()
                        })
            else
                this.$store.dispatch("resources/updateResourceAttr", {
                    attrName: this.tab,
                    index: this.editedIndex,
                    attrs: this.editedItem
                }).then(() => {
                    this.loading = false
                    this.closeEdit()
                })
        },
        deleteItem(item) {
            this.dialogDelete = true
        }
    },
    mounted() {
        this.loadResource()
    }
}
</script>