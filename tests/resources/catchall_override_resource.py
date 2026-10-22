from bottler import Resource


class CatchallOverrideResource(Resource):
    """A root-mounted catch-all (like a real SPA/static-file resource) that
    opts out of api_prefix -- regression fixture for the bug where this
    resource's own dynamic /<path:path> route could shadow a real,
    default-prefixed dynamic API route (e.g. a DB auto-CRUD /<table>/<key>)
    based on Bottle's first-match-wins dynamic-route registration order."""

    api_prefix = ""

    def options(self):
        pass

    def get(self, path=None):
        return {"caught_by": "catchall_override_resource", "path": path}
