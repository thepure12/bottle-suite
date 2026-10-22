from bottler import Resource
from . import _shared


class RelativeImportResource(Resource):

    def options(self):
        pass

    def get(self):
        return {"greeting": _shared.GREETING}

    def post(self):
        return self.get()

    def put(self):
        return self.get()

    def patch(self):
        return self.get()

    def delete(self):
        pass
