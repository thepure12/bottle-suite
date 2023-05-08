from __future__ import annotations
from bottle_rest import Resource
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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

class Config(Resource):
    def __init__(self, app: BottleSuite) -> None:
        super().__init__()
        self.app = app

    def get(self):
        return self.app.cfg


class DataTypes(Resource):
    def __init__(self, app: BottleSuite) -> None:
        super().__init__()
        self.app = app

    def get(self):
        if self.app.sqlite:
            return {"datatypes": SQLITE_TYPES}


class AllResources(Resource):
    def __init__(self, app: BottleSuite) -> None:
        super().__init__()
        self.app = app

    def options(self):
        pass

    def get(self, resource=None):
        if resource:
            res_data = next(
                {"name": name, "fields": table}
                for name, table in self.app.getDBTables().items()
                if name == resource
            )
            config = self.app.cfg.get("resources", {}).get(resource, {})
            cfg_paths = config.get("paths", [])
            res_data["paths"] = [p for p in cfg_paths]
            for r in self.app.routes:
                if resource in r.rule and r.rule not in res_data["paths"]:
                    res_data["paths"].append(r.rule)
            res_data["paths"] = [
                {"path": p, "index": i} for i, p in enumerate(res_data["paths"])
            ]
            roles = {k: v for k, v in config.get("roles", {}).items()}
            for method in ["get", "post", "put", "patch", "delete"]:
                if method not in roles:
                    roles[method] = False
            res_data["roles"] = [{"method": k, "roles": v} for k, v in roles.items()]
            return res_data
        else:
            resources = {}
            for r in self.app.rest.resources:
                name = getattr(r, "name", r.__class__.__name__)
                table = getattr(r, "table", None)
                if name in resources:
                    if table:
                        # TODO handle resource with multiple tables
                        resources[name] = table
                elif table:
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
        self.app.createTable(name),
        return {"id": name, "name": "".join(p.capitalize() for p in name.split("_"))}

    def patch(self, resource, attr_name, value):
        attr_name = attr_name.lower()
        if attr_name == "roles":
            method = value["method"].lower()
            roles = value["roles"]
            self.app.updateRoles(resource, method, roles)
        elif attr_name == "paths":
            index = value["index"]
            path = value["path"]
            self.app.updatePaths(resource, index, path)
        elif attr_name == "fields":
            self.app.alterDBTable(resource, value)
