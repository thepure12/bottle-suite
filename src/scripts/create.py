import argparse
import os
import toml
import secrets
import shutil
import pathlib
import sqlite3

from bottle_suite import resource_scaffold


class Colors:
    """ANSI color codes"""

    BLACK = "\033[0;30m"
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    BROWN = "\033[0;33m"
    BLUE = "\033[0;34m"
    PURPLE = "\033[0;35m"
    CYAN = "\033[0;36m"
    LIGHT_GRAY = "\033[0;37m"
    DARK_GRAY = "\033[1;30m"
    LIGHT_RED = "\033[1;31m"
    LIGHT_GREEN = "\033[1;32m"
    YELLOW = "\033[1;33m"
    LIGHT_BLUE = "\033[1;34m"
    LIGHT_PURPLE = "\033[1;35m"
    LIGHT_CYAN = "\033[1;36m"
    LIGHT_WHITE = "\033[1;37m"
    BOLD = "\033[1m"
    FAINT = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    NEGATIVE = "\033[7m"
    CROSSED = "\033[9m"
    END = "\033[0m"


cfg = {
    "cors": True,
    "jwt": secrets.token_urlsafe(32),
    "sql": False,
    "sqlite": False,
    "rest": True,
    "resources": {
        "hello_world": {
            "paths": ["/", "/hello_world", "/hello_world/<hello_id>"],
            "roles": {
                "get": False,
                "post": True,
                "put": True,
                "patch": True,
                "delete": True,
            },
        }
    },
}


def colored(text: str, color: Colors):
    return f"{color}{text}{Colors.END}"


def cprint(text: str, color: Colors):
    print(colored(text, color))


def getProjectDir(args):
    dirname = args.dirname
    if not dirname:
        try:
            dirname = input(
                f"Enter project name. {colored('<bottle-suite-project>', Colors.DARK_GRAY)}: "
            )
        except KeyboardInterrupt:
            print("")
            exit()
    if not dirname:
        dirname = "bottle-suite-project"
    return dirname


def createProjectDir(dirname):
    try:
        os.mkdir(dirname)
        os.mkdir(f"{dirname}/resources")
        with open(f"{dirname}/bottle_suite.toml", "w+") as f:
            toml.dump(cfg, f)
        path = f"{pathlib.Path(__file__).parent.resolve()}"
        shutil.copyfile(f"{path}/hello_world.py", f"{dirname}/resources/hello_world.py")
    except FileExistsError as e:
        cprint(f"(error) {e} already exists.", Colors.RED)
        exit()
    except FileNotFoundError as e:
        cprint(f"(error) {e} not found.", Colors.RED)
        exit()


def createSqliteDB(dirname: str):
    create = (
        "y"
        == input(
            f"Create a SQLite database? {colored('[y/N]', Colors.DARK_GRAY)}: "
        ).lower()
    )
    if create:
        dflt = dirname.replace("-", "_")
        db_name = input(
            f"Enter database name. {colored(f'<{dflt}>', Colors.DARK_GRAY)}: "
        )
        if not db_name:
            db_name = dflt
        conn = sqlite3.connect(f"{dirname}/{db_name}.db")
        conn.close()
        cfg["sqlite"] = db_name + ".db"
        with open(f"{dirname}/bottle_suite.toml", "w+") as f:
            toml.dump(cfg, f)
        return True
    else:
        return False


def attachSqlDB(dirname):
    attachSqlDB = (
        "y"
        == input(
            f"Attach an SQL database? {colored('[y/N]', Colors.DARK_GRAY)}: "
        ).lower()
    )
    if attachSqlDB:
        cfg["sql"] = {
            "host": input(f"Enter host name. {colored('<localhost>', Colors.DARK_GRAY)}")
            or "my.db.com",
            "database": input(f"Enter database name. {colored('<mydb>', Colors.DARK_GRAY)}")
            or "mydb",
            "user": input(f"Enter username. {colored('<username>', Colors.DARK_GRAY)}")
            or "username",
            "password": input(f"Enter password. {colored('<password>', Colors.DARK_GRAY)}")
            or "password",
        }
        with open(f"{dirname}/bottle_suite.toml", "w+") as f:
            toml.dump(cfg, f)


def setupDashboardAuth(dirname):
    setup = (
        "y"
        == input(
            f"Set up a dashboard admin password? {colored('[y/N]', Colors.DARK_GRAY)}: "
        ).lower()
    )
    if setup:
        from bottle_suite.dashboard.resources.token import hashPassword

        username = (
            input(f"Enter admin username. {colored('<admin>', Colors.DARK_GRAY)}: ")
            or "admin"
        )
        password = input("Enter admin password: ")
        if not password:
            cprint(
                "(error) Password cannot be empty, skipping dashboard setup.",
                Colors.RED,
            )
            return
        cfg["dashboard"] = {"username": username, "password_hash": hashPassword(password)}
        with open(f"{dirname}/bottle_suite.toml", "w+") as f:
            toml.dump(cfg, f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dirname", nargs="?")
    args = parser.parse_args()
    dirname = getProjectDir(args)
    createProjectDir(dirname)
    if not createSqliteDB(dirname):
        attachSqlDB(dirname)
    setupDashboardAuth(dirname)
    print(f"Created project {dirname}")
    cprint(f"\n\tcd {dirname}\n\tbottle-suite -d -r\n\t", Colors.DARK_GRAY)


def getResourceName(args):
    name = args.resource
    if not name:
        try:
            name = input(
                f"Enter resource name. {colored('<my_resource>', Colors.DARK_GRAY)}: "
            )
        except KeyboardInterrupt:
            print("")
            exit()
    return name.strip().lower()


def createResourceFile(name):
    if not resource_scaffold.NAME_RE.match(name):
        cprint(f"(error) Invalid resource name: {name}", Colors.RED)
        exit()
    resources_dir = os.path.join(os.getcwd(), "resources")
    try:
        resource_scaffold.writeResourceFile(resources_dir, name)
    except FileExistsError as e:
        cprint(f"(error) {e}.", Colors.RED)
        exit()


def updateResourceConfig(name):
    cfg_path = os.path.join(os.getcwd(), "bottle_suite.toml")
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            project_cfg = toml.load(f)
    else:
        project_cfg = {}
    project_cfg.setdefault("resources", {}).setdefault(name, {})[
        "paths"
    ] = resource_scaffold.defaultPaths(name)
    with open(cfg_path, "w") as f:
        toml.dump(project_cfg, f)


def resource():
    parser = argparse.ArgumentParser()
    parser.add_argument("resource", nargs="?")
    args = parser.parse_args()
    name = getResourceName(args)
    createResourceFile(name)
    updateResourceConfig(name)
    print(f"Created resource {name}")
    cprint(f"resources/{name}.py", Colors.DARK_GRAY)
