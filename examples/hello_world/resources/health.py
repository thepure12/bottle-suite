from bottler import Resource


class Health(Resource):
    # No [resources.health] section in bottler.toml, so the path is the
    # module name: /health.
    def get(self):
        return {"status": "ok"}
