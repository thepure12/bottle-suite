from bottle_suite import Resource


class Health(Resource):
    # No [resources.health] section in bottle_suite.toml -- this falls back
    # to BottleSuite's default path convention (/<module_name>), unlike
    # project_tasks.py/project_summary.py which configure a custom path.
    def get(self):
        return {"status": "ok"}
