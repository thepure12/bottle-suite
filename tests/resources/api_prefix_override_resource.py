from bottler import Resource


class ApiPrefixOverrideResource(Resource):
    """Exercises importResourcesFromFile()'s per-resource api_prefix
    override -- opts out of Bottler's global api_prefix entirely, the
    way a root-mounted SPA/static-file resource needs to."""

    api_prefix = ""

    def options(self):
        pass

    def get(self):
        return {}
