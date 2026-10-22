from bottle_suite import Resource
from bottle import response, request, redirect


class HelloWorld(Resource):
    def __init__(self) -> None:
        super().__init__()
        self.hello_worlds = [{"hello_id": str(i)} for i in range(10)]

    @property
    def next_id(self):
        return max([i for i in self.hello_worlds["hello_id"]]) + 1

    def _getById(self, hello_id):
        return next(
            filter(lambda x: x["hello_id"] == hello_id, self.hello_worlds), None
        )

    def get(self, hello_id=None):
        if request.path == "/":
            redirect("/hello_world")
        if hello_id:
            resource = self._getById(hello_id)
            if resource:
                return resource
            else:
                response.status = 404
                return {"message": "Resource not found"}
        else:
            return {"hello_worlds": self.hello_worlds}

    def post(self, hello_id=None):
        if self._getById(hello_id):
            response.status = 404
            return {"message": "Resource already exits"}
        else:
            if not hello_id:
                hello_id = self.next_id
            self.hello_worlds.append({"hello_id": hello_id})
            response.status = 201
            return self._getById(hello_id)

    def put(self, hello_id, new_id):
        resource = self._getById(hello_id)
        if resource:
            resource["hello_id"] = new_id
            return resource
        else:
            self.hello_worlds.append({"hello_id": hello_id})
            response.status = 201
            return self._getById(hello_id)

    def patch(self, hello_id, new_id):
        return self.put(hello_id, new_id)

    def delete(self, hello_id):
        try:
            i = self.hello_worlds.index({"hello_world": hello_id})
        except ValueError:
            response.status = 404
            return {"message": "Resource not found"}
        except Exception as e:
            response.status = 500
            return {"message": f"{e}"}
        else:
            self.hello_worlds.pop(i)
            return {"message": "Deleted"}
