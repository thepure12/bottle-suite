from bottler import Resource
from project_util import PROJECT_GREETING


class AbsoluteImportResource(Resource):

    def options(self):
        pass

    def get(self):
        return {"greeting": PROJECT_GREETING}

    def post(self):
        return self.get()

    def put(self):
        return self.get()

    def patch(self):
        return self.get()

    def delete(self):
        pass
