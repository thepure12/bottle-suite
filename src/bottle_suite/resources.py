from __future__ import annotations
from .plugins import Resource
import sqlite3
import pymysql
import toml
import os
from typing import TYPE_CHECKING
from bottle import response

if TYPE_CHECKING:  # pragma: no cover -- never True at runtime
    from .bottle_suite import BottleSuite

SQLITE_TYPES = [
    "INT",
    "INTEGER",
    "TINYINT",
    "SMALLINT",
    "MEDIUMINT",
    "BIGINT",
    "UNSIGNED BIGINT",
    "INT2",
    "INT8",
    "CHARACTER(20)",
    "VARCHAR(255)",
    "VARYINGCHARACTER(255)",
    "NCHAR(55)",
    "NATIVE CHARACTER(70)",
    "NVARCHAR(100)",
    "TEXT",
    "CLOB",
    "REAL",
    "DOUBLE",
    "DOUBLE PRECISION",
    "FLOAT",
    "NUMERIC",
    "DECIMAL(10,5)",
    "BOOLEAN",
    "DATE",
    "DATETIME",
]

MYSQL_TYPES = [
    "TINYINT",
    "SMALLINT",
    "MEDIUMINT",
    "INT",
    "BIGINT",
    "DECIMAL",
    "FLOAT",
    "DOUBLE",
    "BIT",
    "BOOLEAN",
    "CHAR",
    "VARCHAR(255)",
    "TINYTEXT",
    "TEXT",
    "MEDIUMTEXT",
    "LONGTEXT",
    "BLOB",
    "DATE",
    "DATETIME",
    "TIMESTAMP",
    "TIME",
    "YEAR",
    "JSON",
    "ENUM",
]

def _buildRoles(config: dict) -> list:
    roles = {k: v for k, v in config.get("roles", {}).items()}
    for method in ["get", "post", "put", "patch", "delete"]:
        if method not in roles:
            roles[method] = False
    return [{"method": k, "roles": v} for k, v in roles.items()]


class Config(Resource):
    def __init__(self, app: BottleSuite) -> None:
        super().__init__()
        self.app = app

    def options(self):
        pass

    def get(self):
        return toml.dumps(self.app.cfg)

    def put(self, config):
        try:
            config = toml.loads(config)
            self.app.cfg.clear()
            self.app.cfg.update(config)
            self.app.saveConfig()
            self.app.reloadServer()
        except Exception as e:
            response.status = 400
            return {"message": str(e)}

class DataTypes(Resource):
    def __init__(self, app: BottleSuite) -> None:
        super().__init__()
        self.app = app

    def options(self):
        pass

    def get(self):
        if self.app.sqlite:
            return {"datatypes": SQLITE_TYPES}
        elif self.app.sql:
            return {"datatypes": MYSQL_TYPES}


class AllResources(Resource):

    

    def __init__(self, app: BottleSuite) -> None:
        super().__init__()
        self.app = app

    def options(self):
        pass

    def get(self, resource=None):
        if resource:
            tables = self.app.getDBTables()
            lower_tables = {t.lower(): t for t in tables}
            matched = lower_tables.get(resource.lower())
            if matched is None:
                response.status = 404
                return {
                    "message": f"Resource '{resource}' not found. Known DB tables: {list(tables.keys())}"
                }
            resource = matched
            res_data = {"name": resource, "fields": tables[resource]}
            config = self.app.cfg.get("resources", {}).get(resource, {})
            cfg_paths = config.get("paths", [])
            res_data["paths"] = [p for p in cfg_paths]
            for r in self.app.routes:
                if resource in r.rule and r.rule not in res_data["paths"]:
                    res_data["paths"].append(r.rule)
            res_data["paths"] = [
                {"path": p, "index": i} for i, p in enumerate(res_data["paths"])
            ]
            res_data["roles"] = _buildRoles(config)
            return res_data
        else:
            resources = {}
            for r in self.app.rest.resources:
                name = getattr(r, "name", r.__class__.__name__)
                table = getattr(r, "table", None)
                if not table:
                    continue
                if name in resources and resources[name] != table:
                    # Same resource name but a different backing table -- keep
                    # both instead of letting the later one silently overwrite
                    # the earlier one's entry.
                    name = f"{name} ({table})"
                resources[name] = table

            return {
                "resources": [
                    {
                        "name": n,
                        "id": t,
                    }
                    for n, t in resources.items()
                ]
            }

    def post(self, name):
        try:
            name = self.app.createTable(name)
        except (ValueError, sqlite3.OperationalError) as e:
            response.status = 400
            return {"message": str(e)}
        return {"id": name, "name": "".join(p.capitalize() for p in name.split("_"))}

    def patch(self, resource, attr_name, value):
        attr_name = attr_name.lower()
        try:
            if attr_name == "roles":
                method = value["method"].lower()
                roles = value["roles"]
                self.app.updateRoles(resource, method, roles)
            elif attr_name == "paths":
                index = value["index"]
                path = value["path"]
                self.app.updatePaths(resource, index, path)
            elif attr_name == "remove_path":
                index = value["index"]
                self.app.removePath(resource, index)
            elif attr_name == "fields":
                self.app.alterDBTable(resource, value)
        except KeyError as e:
            response.status = 400
            return {"message": f"Missing expected key: {e}"}
        except (ValueError, sqlite3.OperationalError, RuntimeError) as e:
            response.status = 400
            return {"message": str(e)}

    def delete(self, resource):
        tables = self.app.getDBTables()
        lower_tables = {t.lower(): t for t in tables}
        matched = lower_tables.get(resource.lower())
        if matched is None:
            response.status = 404
            return {
                "message": f"Resource '{resource}' not found. Known DB tables: {list(tables.keys())}"
            }
        try:
            self.app.dropTable(matched)
        except (ValueError, sqlite3.OperationalError, pymysql.err.OperationalError) as e:
            response.status = 400
            return {"message": str(e)}
        return {"message": f"{matched} deleted"}


class PythonResources(Resource):
    def __init__(self, app: BottleSuite) -> None:
        super().__init__()
        self.app = app

    def options(self):
        pass

    def _listNames(self):
        resources_dir = os.path.join(os.getcwd(), "resources")
        names = []
        if os.path.isdir(resources_dir):
            names = sorted(
                f[:-3]
                for f in os.listdir(resources_dir)
                if f.endswith(".py") and f != "__init__.py"
            )
        return names

    def get(self, resource=None):
        names = self._listNames()
        if resource:
            if resource not in names:
                response.status = 404
                return {
                    "message": f"Resource '{resource}' not found. Known Python resources: {names}"
                }
            config = self.app.cfg.get("resources", {}).get(resource, {})
            cfg_paths = config.get("paths", [f"/{resource}"])
            paths = [{"path": p, "index": i} for i, p in enumerate(cfg_paths)]
            return {"name": resource, "paths": paths, "roles": _buildRoles(config)}
        return {"resources": [{"name": n} for n in names]}

    def post(self, name):
        try:
            created = self.app.createResourceFile(name)
        except (ValueError, FileExistsError) as e:
            response.status = 400
            return {"message": str(e)}
        return {"name": created}

    def patch(self, resource, attr_name, value):
        attr_name = attr_name.lower()
        try:
            if attr_name == "roles":
                method = value["method"].lower()
                roles = value["roles"]
                self.app.updateRoles(resource, method, roles)
            elif attr_name == "paths":
                index = value["index"]
                path = value["path"]
                self.app.updatePaths(resource, index, path)
            elif attr_name == "remove_path":
                index = value["index"]
                self.app.removePath(resource, index)
        except KeyError as e:
            response.status = 400
            return {"message": f"Missing expected key: {e}"}

    def delete(self, resource):
        names = self._listNames()
        if resource not in names:
            response.status = 404
            return {
                "message": f"Resource '{resource}' not found. Known Python resources: {names}"
            }
        self.app.deleteResourceFile(resource)
        return {"message": f"{resource} deleted"}
