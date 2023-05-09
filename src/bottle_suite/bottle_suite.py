# Bottle and plugins
from bottle import Bottle
from bottle_cors import EnableCors
from bottle_rest import API, Resource
from bottle_jwt import JWTPlugin, authFunc
from bottle_sql import sqlitePlugin, sqlPlugin

# Other imports
from typing import Union
import toml
import os
import inspect
from importlib import util
from . import resource_factory, reload
from .resources import AllResources, DataTypes, Config
import pymysql
import pymysql.cursors
import sqlite3


class BottleSuite(Bottle):
    def __init__(
        self,
        cors: bool = True,
        rest: bool = True,
        jwt: Union[bool, str, dict] = "default",
        sqlite: Union[bool, str, dict] = False,
        sql: Union[bool, str, dict] = False,
        gen_db: bool = True,
        gen_res: bool = True,
        cfg_file: str = "bottle_suite.toml",
        run_args: dict = {},
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.cfg_file = cfg_file
        self.run_args = run_args
        try:
            self.cfg = toml.load(cfg_file)
        except:
            self.cfg = {}
        if "cors" in self.cfg:
            cors = self.cfg["cors"]
        if "rest" in self.cfg:
            rest = self.cfg["rest"]
        if "jwt" in self.cfg:
            jwt = self.cfg["jwt"]
        if "sqlite" in self.cfg:
            sqlite = self.cfg["sqlite"]
        if "sql" in self.cfg:
            sql = self.cfg["sql"]
        self.setupCors(cors)
        if sql and sqlite:
            # TODO allow multiple databases
            raise Exception("Cannot use both sql and sqlite")
        self.setupSql(sql)
        self.setupSqlite(sqlite)
        self.setupJwt(jwt)
        self.setupRest(rest, gen_res)
        if gen_db and (sql or sqlite):
            self.createResForDB()

    @property
    def resource_names(self):
        try:
            return set([r.name for r in self.rest.resources])
        except:
            return set()

    def setupCors(self, cors):
        if cors:
            self.cors = EnableCors()
            self.install(self.cors)
        else:
            self.cors = None

    def setupRest(self, rest, gen: bool):
        if rest:
            self.rest = API()
            self.install(self.rest)
            if gen and os.path.exists(os.getcwd() + "/resources"):
                for py_file in os.listdir(os.getcwd() + "/resources"):
                    self.importResourcesFromFile(py_file)
            self.rest.addResource(
                AllResources(self), "/_resources", "/_resources/<resource>"
            )
            self.rest.addResource(DataTypes(self), "/_datatypes")
            self.rest.addResource(Config(self), "/bottle_suite_cfg")
        else:
            self.rest = None

    def setupJwt(self, jwt):
        cfg = {}
        if jwt:
            if type(jwt) == str:
                cfg["jwt_key"] = jwt
            elif type(jwt) == dict:
                cfg = jwt
            self.jwt = JWTPlugin(**cfg)
            self.install(self.jwt)
            # Create default token callbacks
            for path, callback in self.jwt.token_paths.items():
                self.route("/" + path, "GET", callback)
                self.route("/" + path, "POST", callback)
                self.route("/" + path, "OPTIONS", callback)
                self.route(
                    "/users/current", ["OPTIONS", "GET"], lambda: {"user": "default"}
                )
        else:
            self.jwt = None

    def setupSql(self, sql):
        cfg = {}
        if sql:
            pymysql.converters.conversions[pymysql.FIELD_TYPE.BIT] = (
                lambda x: x == b"\x01"
            )
            if type(sql) == str:
                cfg["database"] = sql
            elif type(sql) == dict:
                cfg = sql
            self.sql = sqlPlugin(**cfg)
            self.install(self.sql)
        else:
            self.sql = None

    def setupSqlite(self, sqlite):
        cfg = {}
        if sqlite:
            if type(sqlite) == str:
                cfg["database"] = sqlite
            elif type(sqlite) == dict:
                cfg = sqlite
            self.sqlite = sqlitePlugin(**cfg)
            self.install(self.sqlite)
        else:
            self.sqlite = None

    def setTokenAuthFunction(self, func=None, token_path="token"):
        if not func:
            func = authFunc
        self.jwt.token_paths[token_path] = func

    def importResourcesFromFile(self, py_file):
        module_name = py_file[:-3]
        if module_name == "__init__" or py_file[-3:] != ".py":
            return
        spec = util.spec_from_file_location(
            module_name, f"{os.getcwd()}/resources/{py_file}"
        )
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)
        classes = inspect.getmembers(module, inspect.isclass)
        for cls in classes:
            resource = cls[1]
            if cls[0] == "Resource":
                continue
            try:
                paths = self.cfg["resources"][module_name]["paths"]
            except:
                paths = [f"/{module_name}"]
            self.setRoles(resource, module_name)
            self.rest.addResource(cls[1], *paths)

    def setRoles(self, resource, name):
        for meth in resource.Methods:
            route_cfg = resource.getRouteConfig(meth)
            try:
                if "roles" in route_cfg:
                    route_cfg["roles"] += self.cfg["resources"][name]["roles"][
                        meth.value.lower()
                    ]
                else:
                    route_cfg["roles"] = self.cfg["resources"][name]["roles"][
                        meth.value.lower()
                    ]
            except KeyError as e:
                pass
            except Exception as e:
                print(f"Skipping roles on {meth.value} for {resource}: {type(e)} - {e}")
            resource.setRouteConfig(meth, route_cfg)

    def createResForDB(self):
        rules = {r.rule for r in self.routes}
        if self.rest and (self.sql or self.sqlite):
            for table, fields in self.getDBTables().items():
                resource = resource_factory.createResource(table, fields, self.sql)
                self.setRoles(resource, table)
                endpoints = []
                if f"/{table}" not in rules:
                    endpoints = [f"/{table}"]
                if resource.key and f"/{table}/<key>" not in rules:
                    endpoints.append(f"/{table}/<key>")
                try:
                    for path in self.cfg["resources"][table]["paths"]:
                        if path not in rules:
                            endpoints.append(path)
                except KeyError:
                    pass
                if endpoints:
                    self.rest.addResource(resource, endpoints)
        else:
            # TODO raise error
            pass

    def getSqlTable(self, db, table) -> list:
        db.execute(f"DESCRIBE {table}")
        return [
            {
                "field": r[0],
                "type": r[1],
                "null": r[2],
                "key": r[3],
                "default": r[4],
                "extra": r[5],
            }
            for r in db.fetchall()
        ]

    def getSqliteTable(self, db, table):
        return db.execute(f"PRAGMA table_info('{table['name']}')").fetchall()

    def getDBTable(self, db, table: str) -> list:
        keys = {
            None: 0,
            "": 0,
            "PRI": 1,
            "MUL": 0,  # TODO
            "UNI": 0,  # TODO
        }
        try:
            db.execute(f"PRAGMA table_info('{table}')")
        except:
            db.execute(f"DESCRIBE {table}")
        return [
            {
                "name": r.get("name") or r.get("Field"),
                "type": r.get("type") or r.get("Type"),
                "notnull": r.get("notnull") == 1 or r.get("Null") == "NO",
                "default": r.get("dflt_value") or r.get("Default"),
                "key": r.get("pk") or keys[r.get("Key")],
            }
            for r in db.fetchall()
        ]

    def getDBTables(self) -> dict:
        try:
            conn = sqlite3.connect(self.sqlite.sql_config["database"])
            conn.row_factory = lambda cursor, row: {
                col[0]: row[idx] for idx, col in enumerate(cursor.description)
            }
        except:
            conn = pymysql.connect(
                host=self.sql.sql_config["host"],
                user=self.sql.sql_config["user"],
                password=self.sql.sql_config["password"],
                database=self.sql.sql_config["database"],
                cursorclass=pymysql.cursors.DictCursor,
            )
        db = conn.cursor()
        if isinstance(db, sqlite3.Cursor):
            tables_sql = "SELECT name FROM sqlite_master WHERE type='table' AND sql LIKE '%PRIMARY%'"
        elif isinstance(db, pymysql.cursors.Cursor):
            tables_sql = f"SELECT table_name as name FROM information_schema.tables WHERE table_schema = '{self.sql.sql_config['database']}'"
        db.execute(tables_sql)
        table_rows = db.fetchall()
        name = lambda table: table.get("name") or table.get("Name")
        tables = {name(table): self.getDBTable(db, name(table)) for table in table_rows}
        db.close()
        conn.close()
        return tables

    def createTable(self, name):
        sql = f"""CREATE TABLE {name} (
                  {name}_id INTEGER PRIMARY KEY AUTOINCREMENT)"""
        if self.sqlite:
            print(f"Creating table {name}")
            with sqlite3.connect(self.sqlite.dbfile) as db:
                created = db.execute(sql)
                db.commit()
        self.reloadServer()

    def alterDBTable(self, table, field_attrs):
        print(f"Altering {table} with {field_attrs}")
        if self.sqlite:
            with sqlite3.connect(self.sqlite.dbfile) as db:
                fields = self.getSqliteTable(db, {"name": table})
                (cid, name, datatype, notnull, dflt, pk) = next(
                    (f for f in fields if f[0] == field_attrs["cid"]),
                    (
                        None,
                        field_attrs["name"],
                        field_attrs["type"],
                        field_attrs["notnull"],
                        field_attrs["dflt_value"],
                        field_attrs["pk"],
                    ),
                )
                print(name)
                if cid or cid == 0:
                    sql = f"""ALTER TABLE {table}
                              RENAME COLUMN {name} TO {field_attrs['name']}"""
                    db.execute(sql)
                elif name:
                    datatype = datatype or "TEXT"
                    notnull = "NOT NULL" if notnull else ""
                    if notnull and not dflt:
                        dflt = " "
                    dflt = f"DEFAULT {dflt}" if dflt else ""
                    pk = "PRIMARY KEY" if pk == 1 else ""
                    sql = f"""ALTER TABLE {table}
                              ADD COLUMN {name} {datatype} {dflt} {notnull} {pk}"""
                    db.execute(sql)
                db.commit()
        self.reloadServer()

    def getResourceConfig(self, resource: str) -> dict:
        try:
            cfg_resource = self.cfg["resources"][resource]
        except:
            cfg_resource = self.cfg["resources"][resource] = {}
        return cfg_resource

    def updatePaths(self, resource, index, path):
        print(f"Updating paths for {resource}")
        cfg_resource = self.getResourceConfig(resource)
        if "paths" not in cfg_resource:
            cfg_resource["paths"] = []
        try:
            cfg_resource["paths"][index] = path
        except (IndexError, TypeError) as e:
            cfg_resource["paths"].append(path)
        self.saveConfig()
        self.reloadServer()

    def updateRoles(self, resource: str, method: str, roles: Union[list, str]):
        print(f"Updating roles for {resource}")
        cfg_resource = self.getResourceConfig(resource)
        if "roles" in cfg_resource:
            cfg_roles = cfg_resource["roles"]
        else:
            cfg_roles = cfg_resource["roles"] = {method: False}
        if roles.lower() in ["true", "false"]:
            cfg_roles[method] = roles == "true"
        else:
            cfg_roles[method] = roles.split(",")
        self.saveConfig()
        self.reloadServer()

    def saveConfig(self):
        try:
            with open(self.cfg_file, "w+") as f:
                toml.dump(self.cfg, f)
        except Exception as e:
            print(e)

    def reloadServer(self):
        # Only reload if reloader is set to true
        with open(reload.__file__, "w") as f:
            f.write("# Used to force reload")
