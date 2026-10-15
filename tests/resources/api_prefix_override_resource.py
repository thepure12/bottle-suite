from bottle_suite import Resource


class ApiPrefixOverrideResource(Resource):
    """Exercises importResourcesFromFile()'s per-resource api_prefix
    override -- opts out of BottleSuite's global api_prefix entirely, the
    way a root-mounted SPA/static-file resource needs to."""

    api_prefix = ""

    def options(self):
        pass

    def get(self):
        return {}
