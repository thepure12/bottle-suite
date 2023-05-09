<template>
  <v-app dark>
    <v-navigation-drawer v-model="drawer" :mini-variant="miniVariant" :clipped="clipped" fixed app>
      <v-list>
        <v-list-item v-for="(item, i) in items" :key="i" :to="item.to" router exact>
          <v-list-item-action>
            <v-icon>{{ item.icon }}</v-icon>
          </v-list-item-action>
          <v-list-item-content>
            <v-list-item-title>
              {{ item.title }}
            </v-list-item-title>
          </v-list-item-content>
        </v-list-item>
      </v-list>
    </v-navigation-drawer>
    <v-app-bar :clipped-left="clipped" fixed app>
      <v-app-bar-nav-icon @click.stop="drawer = !drawer" />
      <v-toolbar-title>{{ title }}</v-toolbar-title>
      <v-spacer />
    </v-app-bar>
    <v-main>
      <v-container>
        <Toast ref="vtoast" />
        <Nuxt />
      </v-container>
    </v-main>
    <v-footer :absolute="!fixed" app>
      <span>&copy; {{ new Date().getFullYear() }}</span>
    </v-footer>
  </v-app>
</template>

<script>
import Toast from '~/components/Toast.vue';

export default {
  data() {
    return {
      clipped: true,
      drawer: false,
      fixed: false,
      items: [
        {
          icon: "mdi-apps",
          title: "Welcome",
          to: "/"
        },
        {
          icon: "mdi-package-variant-closed",
          title: "DB Resources",
          to: "/resources"
        },
        {
          icon: "mdi-cog",
          title: "Config",
          to: "/config"
        }
      ],
      miniVariant: false,
      title: "Bottle Suite"
    };
  },
  mounted() {
    this.$root.vtoast = this.$refs.vtoast;
  },
  components: { Toast }
}
</script>
<style>
.v-input--reverse .v-input__slot {
  flex-direction: row-reverse;
  justify-content: flex-end;
}

.v-application--is-ltr .v-input--reverse .v-input__slot .v-input--selection-controls__input {
  margin-right: 0;
  margin-left: 8px;
}

.v-application--is-rtl .v-input--reverse .v-input__slot .v-input--selection-controls__input {
  margin-left: 0;
  margin-right: 8px;
}

.v-input--reverse .v-input__slot>.v-label,
.v-input--selection-controls .v-radio>.v-label {
  flex: none;
}
</style>