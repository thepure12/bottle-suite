import os

TEMPLATE = '''def authenticate(username=None, password=None, **kwargs):
    """
    Auto-wired as the JWT /token auth function if this file (auth.py) is
    present at the project root and defines a callable "authenticate".
    Return a truthy dict payload (e.g. {"user": ..., "roles": [...]}) on
    success -- it's encoded into the issued JWT -- or a falsy value to
    reject the login attempt. This stub rejects everything by default; see
    example/app.py in the bottle_suite repo for a real PBKDF2-based
    implementation to build from.
    """
    return None
'''


def writeAuthFile(project_dir: str) -> str:
    """Write auth.py from the template. Raises FileExistsError if it's already there."""
    file_path = os.path.join(project_dir, "auth.py")
    if os.path.exists(file_path):
        raise FileExistsError("auth.py already exists")
    with open(file_path, "w") as f:
        f.write(TEMPLATE)
    return file_path
