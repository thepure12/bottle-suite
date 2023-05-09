<template>
    <v-snackbar
        :color="color"
        :timeout="timer"
        v-model="showSnackbar"
        dismassable
        top
        right
    >
      <v-icon left>{{icon}}</v-icon>
      <span class="text-subtitle-1 font-weight-medium">{{message}}</span>
    </v-snackbar>
  </template>
  
  <script>
  export default {
    name: "vtoast",
    data() {
      return{
        showSnackbar: false,
        message: '',
        color: 'success',
        icon: 'mdi-check',
        timer: 5000
      }
    },
    methods:{
      show(data) {
        this.message = data.message || 'missing "message".'
        this.color = data.color || 'success'
        this.timer = data.timer || 3000
        this.icon = data.icon || 'mdi-check'
        this.showSnackbar = true
      }
    }
  }
  </script>