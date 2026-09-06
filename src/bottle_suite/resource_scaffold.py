import os
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


def className(name: str) -> str:
    return "".join(p.capitalize() for p in name.split("_"))


def defaultPaths(name: str) -> list:
    return [f"/{name}", f"/{name}/<key>"]


def writeResourceFile(resources_dir: str, name: str) -> str:
    """Write resources/<name>.py from the template. Raises FileExistsError if it's already there."""
    os.makedirs(resources_dir, exist_ok=True)
    file_path = os.path.join(resources_dir, f"{name}.py")
    if os.path.exists(file_path):
        raise FileExistsError(f"Resource '{name}' already exists")
    with open(file_path, "w") as f:
        f.write(render(className(name)))
    return file_path


def deleteResourceFile(resources_dir: str, name: str) -> None:
    """Remove resources/<name>.py. Raises FileNotFoundError if it isn't there."""
    file_path = os.path.join(resources_dir, f"{name}.py")
    os.remove(file_path)
