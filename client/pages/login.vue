<template>
    <v-container>
        <v-row justify="center">
            <v-card width="100%" max-width="500px">
                <v-toolbar color="light-blue" dark>
                    <v-toolbar-title>Login</v-toolbar-title>
                </v-toolbar>
                <v-card-text>
                    <p class="text-caption white--text">
                        If you have not setup a token path, login with any username and password.
                    </p>
                    <v-form ref="loginForm" class="login" @submit.prevent="doLogin" lazy-validation>
                        <v-text-field label="Username" :rules="rules" required></v-text-field>
                        <v-text-field label="Password" :rules="rules" type="password" required></v-text-field>
                        <v-flex class="d-flex justify-end">
                            <v-btn type="submit" color="light-blue">Login</v-btn>
                        </v-flex>
                    </v-form>
                </v-card-text>
            </v-card>
        </v-row>
    </v-container>
</template>
<script>
export default {
    data: () => ({
        username: "",
        password: "",
        rules: [v => !!v || "This field is required!"]
    }),
    methods: {
        async doLogin() {
            let valid = this.$refs.loginForm.validate()
            if (valid)
                await this.$auth
                    .loginWith("local", {
                        data: {
                            username: this.username,
                            password: this.password,
                        },
                    })
        }
    }
}
</script>