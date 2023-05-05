from bottle_suite import Resource

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
