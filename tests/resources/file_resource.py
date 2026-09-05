from bottle_suite import Resource


class NotAResource:
    """A plain, non-Resource class living alongside FileResource in this
    module -- exercises importResourcesFromFile()'s skip-non-Resource-class
    branch (BottleSuite never registers a route for it)."""

    pass


class FileResource(Resource):

    def options(self):
        pass

    def get(self):
        return {}
    
    def post(self):
        return self.get()
    
    def put(self):
        return self.get()
    
    def patch(self):
        return self.get()

    def delete(self):
        pass
