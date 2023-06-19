from bottle_rest import Resource
import hashlib

class DashboardToken(Resource):

    @classmethod
    def authenticate(cls, username=None, password=None, **kwargs):
        # print(type(db))
        # TODO
        return {"user": "user"}
        user: dict # TODO
        # TODO check if user exists
        salt_key = bytes.fromhex(user["password"])
        salt = salt_key[:32]
        key = salt_key[32:]
        new_key = hashlib.pbkdf2_hmac("sha256", password.encode('utf-8'), salt, 100000)
        if new_key == key:
            # TODO return jwt payload
            pass
        else:
            # TODO set 401
            return {"message": "Authentication failed"}

    def options(self, *args, **kwargs):
        pass

    def post(self, username, password):
        pass

    def get(self):
        pass