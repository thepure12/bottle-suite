from bottle import request
from bottler import Resource


class Me(Resource):
    # No roles here and no toml section, so default_roles applies: any
    # valid token. Served at /api/me.
    def get(self):
        return {"user": request.user["user"], "roles": request.user["roles"]}
