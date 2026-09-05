import re

NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")

TEMPLATE = '''from bottle_suite import Resource


class {class_name}(Resource):
    def get(self, key=None):
        pass

    def post(self):
        pass

    def put(self, key):
        pass

    def patch(self, key):
        pass

    def delete(self, key):
        pass
'''


def render(class_name: str) -> str:
    return TEMPLATE.format(class_name=class_name)
