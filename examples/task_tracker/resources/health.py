from bottler import Resource


class Health(Resource):
    # No [resources.health] section in bottler.toml -- this falls back
    # to Bottler's default path convention (/<module_name>), unlike
    # project_tasks.py/project_summary.py which configure a custom path.
    def get(self):
        return {"status": "ok"}
