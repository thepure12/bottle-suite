# Bottle and plugins
from bottle import Bottle, JSONPlugin, static_file
from .plugins import API, Resource, JWTPlugin, authFunc, sqlitePlugin, sqlPlugin, CorsPlugin

# Other imports
from typing import Union
import toml
import os
import sys
import secrets
import inspect
import importlib
from . import resource_factory, reload, resource_scaffold, openapi
from .resources import AllResources, DataTypes, Config, PythonResources, ResourceRoles
from .dashboard.resources.token import DashboardToken
import pymysql
import pymysql.cursors
import sqlite3
import json
import datetime
from decimal import Decimal
from pathlib import Path


DIST = f"{Path(__file__).parent.parent.resolve()}/bottle_suite/dashboard/dist"


def dashboard(path=""):
    if path:
        rel_path = path.lstrip("/")
        if os.path.isfile(os.path.join(DIST, rel_path)):
            return static_file(rel_path, DIST)
    return static_file("index.html", DIST)


def nuxt(filename):
    # print(filename)
    return static_file(filename, f"{DIST}/_nuxt")


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime) or isinstance(obj, datetime.date):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return f"{obj:.4f}"
        return json.JSONEncoder.default(self, obj)


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
        gen_auth: bool = True,
        cfg_file: str = "bottle_suite.toml",
        dashboard: bool = False,
        openapi: Union[bool, dict] = True,
        run_args: dict = {},
        **kwargs,
    ):
        super().__init__(autojson=False, **kwargs)
        # kwargs can never actually contain "autojson" here -- Bottle.__init__
        # would already have raised "got multiple values for keyword argument
        # 'autojson'" on the line above, since it's also passed literally.
        if kwargs.get("autojson") != False:  # pragma: no branch
            json_plugin = JSONPlugin(
                json_dumps=lambda s: json.dumps(s, cls=JSONEncoder)
            )
            self.install(json_plugin)
        self.cfg_file = cfg_file
        self.run_args = run_args
        try:
            self.cfg = toml.load(cfg_file)
        except:
            self.cfg = {}
        dashboard = self.cfg.get("dashboard", dashboard)
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
        if "openapi" in self.cfg:
            openapi = self.cfg["openapi"]
        dashboard, rest, jwt = self.checkDashboardRequirements(dashboard, rest, jwt)
        self.setupCors(cors)
        if sql and sqlite:
            # Only one DB backend at a time: getDBCursor/getDBTables and every
            # generated resource's bind_char assume a single connection.
            raise Exception("Cannot use both sql and sqlite")
        self.setupSql(sql)
        self.setupSqlite(sqlite)
        self.setupJwt(jwt)
        self.setupAuth(gen_auth)
        self.setupDashboard(dashboard)
        self.setupRest(rest, gen_res)
        if gen_db and (sql or sqlite):
            self.createResForDB()
        self.setupOpenApi(openapi)

    @property
    def resource_names(self):
        try:
            return set([r.name for r in self.rest.resources])
        except:
            return set()

    def checkDashboardRequirements(self, dashboard, rest, jwt):
        if isinstance(dashboard, dict):
            enabled = dashboard.get("enabled", True)
        else:
            enabled = bool(dashboard)
        if not enabled or (rest and jwt):
            return dashboard, rest, jwt
        missing = [name for name, val in (("rest", rest), ("jwt", jwt)) if not val]
        missing_str = " and ".join(missing)
        if sys.stdin.isatty():
            choice = (
                input(
                    f"Dashboard is enabled but {missing_str} "
                    f"{'is' if len(missing) == 1 else 'are'} disabled - the "
                    f"dashboard cannot fully function without both. Enable "
                    f"{missing_str} now? [Y/n]: "
                )
                .strip()
                .lower()
            )
            if choice in ("", "y", "yes"):
                if not rest:
                    rest = True
                    self.cfg["rest"] = True
                if not jwt:
                    jwt = secrets.token_urlsafe(32)
                    self.cfg["jwt"] = jwt
                self.saveConfig()
            else:
                dashboard = False
                print("Dashboard disabled.")
        else:
            raise Exception(
                f"Dashboard requires {missing_str} to be enabled (set "
                f"{missing_str} in {self.cfg_file} or pass to the BottleSuite "
                "constructor), or disable the dashboard."
            )
        return dashboard, rest, jwt

    def setupDashboard(self, use_dashboard: Union[bool, dict]):
        if isinstance(use_dashboard, dict):
            enabled = use_dashboard.get("enabled", True)
        else:
            enabled = bool(use_dashboard)
        if enabled:
            if not os.path.exists(f"{DIST}/index.html"):
                print(
                    f"Dashboard enabled but no build found at {DIST} - run 'make dashboard'"
                )
            self.dashboard_token = DashboardToken(self)
            # checkDashboardRequirements() (called earlier in __init__,
            # before setupJwt) guarantees self.jwt is truthy here whenever
            # the dashboard is enabled - it either already was, the user
            # chose to enable it interactively, or the dashboard itself got
            # disabled instead. The dashboard's bootstrapped admin account
            # (see /dashboard/setup) logs in through its own route, never
            # /token - that endpoint is the project's own API auth,
            # whatever it's wired to, and must never be silently
            # replaced by dashboard credentials. JWTPlugin.apply() keys
            # off route.rule with "/" stripped, so "dashboardtoken" is
            # what "/dashboard/token" collapses to. It's excluded from
            # the OpenAPI spec/`_resources` like the rest of /dashboard.
            self.jwt.addTokenPath("dashboardtoken", self.dashboard_token.authenticate)
            self.route("/dashboard/token", "GET", self.dashboard_token.authenticate)
            self.route("/dashboard/token", "POST", self.dashboard_token.authenticate)
            self.route("/dashboard/token", "OPTIONS", self.dashboard_token.authenticate)
            self.route("/dashboard/_nuxt/<filename>", method="GET", callback=nuxt)
            self.route(
                ["/dashboard", "/dashboard<path:path>"],
                method="GET",
                callback=dashboard,
            )
        else:
            self.dashboard_token = None

    def setupCors(self, cors):
        if cors:
            self.cors = CorsPlugin()
            self.install(self.cors)
        else:
            self.cors = None

    def setupRest(self, rest, gen: bool):
        if rest:
            self.rest = API()
            self.install(self.rest)
            if gen and os.path.exists(os.getcwd() + "/resources"):
                self.importResourcesDir()
            self.rest.addResource(
                AllResources(self), "/_resources", "/_resources/<resource>"
            )
            self.rest.addResource(DataTypes(self), "/_datatypes")
            self.rest.addResource(Config(self), "/bottle_suite_cfg")
            self.rest.addResource(
                PythonResources(self), "/_python_resources", "/_python_resources/<resource>"
            )
            self.rest.addResource(ResourceRoles(self), "/_roles")
            if getattr(self, "dashboard_token", None):
                self.rest.addResource(self.dashboard_token, "/dashboard/setup")
        else:
            self.rest = None

    def setupOpenApi(self, use_openapi: Union[bool, dict]):
        if isinstance(use_openapi, dict):
            enabled = use_openapi.get("enabled", True)
            roles = use_openapi.get("roles")
        else:
            enabled = bool(use_openapi)
            roles = None
        if enabled:
            cfg = {"roles": roles} if roles else {}
            callback = lambda: openapi.buildSpec(self)
            self.route("/openapi.json", "GET", callback, **cfg)
            self.route("/openapi.json", "OPTIONS", callback, **cfg)

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

    def setupAuth(self, gen: bool):
        if not (gen and self.jwt and os.path.exists(os.path.join(os.getcwd(), "auth.py"))):
            return
        # Same temp-sys.path/sys.modules dance as importResourcesDir, scaled
        # down to a single top-level module instead of a package, so repeated
        # BottleSuite() construction against different project dirs in the
        # same process never serves a stale cached auth module.
        project_root = os.getcwd()
        path_added = project_root not in sys.path
        if path_added:
            sys.path.insert(0, project_root)
        try:
            module = importlib.import_module("auth")
        finally:
            if "auth" in sys.modules:
                del sys.modules["auth"]
            if path_added:
                sys.path.remove(project_root)
        func = getattr(module, "authenticate", None)
        if not callable(func):
            print("auth.py found but has no callable 'authenticate' -- skipping")
            return
        self.setTokenAuthFunction(func)

    def importResourcesDir(self):
        # Load resources/ as a real (namespace) package rather than
        # exec'ing each file in isolation, so resource files can use
        # relative imports (from . import helper) or import other modules
        # elsewhere in the project. The project root and cached
        # resources/resources.* modules are cleaned up afterwards so that
        # repeated BottleSuite() instantiations against different projects
        # (tests, the CLI's retry loop) don't leak stale modules or a
        # stale sys.path entry between runs.
        project_root = os.getcwd()
        path_added = project_root not in sys.path
        if path_added:
            sys.path.insert(0, project_root)
        try:
            for py_file in os.listdir(os.path.join(project_root, "resources")):
                self.importResourcesFromFile(py_file)
        finally:
            for name in list(sys.modules):
                if name == "resources" or name.startswith("resources."):
                    del sys.modules[name]
            if path_added:
                sys.path.remove(project_root)

    def importResourcesFromFile(self, py_file):
        module_name = py_file[:-3]
        if module_name == "__init__" or py_file[-3:] != ".py":
            return
        module = importlib.import_module(f"resources.{module_name}")
        classes = inspect.getmembers(module, inspect.isclass)
        for cls in classes:
            if Resource not in cls[1].mro(): # Is class a Bottle-Rest Resource
                continue
            resource = cls[1]
            if cls[0] == "Resource": # Is class the Bottle-Rest base class
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
        if not (self.sql or self.sqlite):
            raise Exception(
                "createResForDB requires a configured database (sql or sqlite)"
            )
        if not self.rest:
            # No REST plugin installed to attach generated resources to --
            # a project can legitimately configure a database without rest.
            return
        rules = {r.rule for r in self.routes}
        for table, fields in self.getDBTables().items():
            if not any(f["key"] == 1 for f in fields):
                print(
                    f"Skipping resource generation for table '{table}': no primary key found"
                )
                continue
            resource = resource_factory.createResource(table, fields, self.sql)
            self.setRoles(resource, table)
            endpoints = []
            if f"/{table}" not in rules:
                endpoints = [f"/{table}"]
            if resource.key and f"/{table}/<key>" not in rules:
                endpoints.append(f"/{table}/<key>")
            # Generic nested-ref route: resource_factory's get() resolves
            # the actual FK relationship (if any) at request time via
            # getRefs, so this single rule covers every table without
            # needing per-relationship routes from getRefEndpoints.
            if f"/<ref_table>/<ref_id>/{table}" not in rules:
                endpoints.append(f"/<ref_table>/<ref_id>/{table}")
            try:
                for path in self.cfg["resources"][table]["paths"]:
                    if path not in rules:
                        endpoints.append(path)
            except KeyError:
                pass
            if endpoints:
                self.rest.addResource(resource, endpoints)

    def getRefEndpoints(self, table):
        sql = resource_factory.FOREIGN_KEY_SQL + f"'{table}'"
        db = self.getDBCursor()
        db.execute(sql)
        refs = db.fetchall()
        endpoints = []
        for ref in refs:
            if ref["referenced_table_name"] != ref["table_name"]:
                e = f"/{ref['referenced_table_name']}/<{ref['referenced_column_name']}>/{table}"
                endpoints.append(e)
        return endpoints

    def getDBCursor(self) -> Union[pymysql.cursors.Cursor, sqlite3.Cursor]:
        if self.sqlite:
            conn = sqlite3.connect(self.sqlite.sql_config["database"])
            conn.row_factory = lambda cursor, row: {
                col[0]: row[idx] for idx, col in enumerate(cursor.description)
            }
        elif self.sql:
            conn = pymysql.connect(
                host=self.sql.sql_config["host"],
                user=self.sql.sql_config["user"],
                password=self.sql.sql_config["password"],
                database=self.sql.sql_config["database"],
                cursorclass=pymysql.cursors.DictCursor,
            )
        else:
            raise Exception("No database configured (sql or sqlite)")
        db = conn.cursor()
        return db

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
            "MUL": 0,  # indexed, non-unique -- not a primary key, no distinct treatment yet
            "UNI": 0,  # unique, non-primary -- not a primary key, no distinct treatment yet
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
        if self.sqlite:
            conn = sqlite3.connect(self.sqlite.sql_config["database"])
            conn.row_factory = lambda cursor, row: {
                col[0]: row[idx] for idx, col in enumerate(cursor.description)
            }
        elif self.sql:
            conn = pymysql.connect(
                host=self.sql.sql_config["host"],
                user=self.sql.sql_config["user"],
                password=self.sql.sql_config["password"],
                database=self.sql.sql_config["database"],
                cursorclass=pymysql.cursors.DictCursor,
            )
        else:
            raise Exception("No database configured (sql or sqlite)")
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
        name = name.strip().lower()
        if not resource_scaffold.NAME_RE.match(name):
            raise ValueError(f"Invalid resource name: {name}")
        sql = f"""CREATE TABLE {name} (
                  {name}_id INTEGER PRIMARY KEY AUTOINCREMENT)"""
        if self.sqlite:
            print(f"Creating table {name}")
            with sqlite3.connect(self.sqlite.sql_config["database"]) as db:
                created = db.execute(sql)
                db.commit()
        self.reloadServer()
        return name

    def dropTable(self, name):
        if name not in self.getDBTables():
            raise ValueError(f"Unknown table: {name}")
        print(f"Dropping table {name}")
        if self.sqlite:
            with sqlite3.connect(self.sqlite.sql_config["database"]) as db:
                db.execute(f"DROP TABLE {name}")
                db.commit()
        else:
            # getDBTables() above already guarantees sqlite or sql is set.
            conn = pymysql.connect(
                host=self.sql.sql_config["host"],
                user=self.sql.sql_config["user"],
                password=self.sql.sql_config["password"],
                database=self.sql.sql_config["database"],
            )
            try:
                cur = conn.cursor()
                cur.execute(f"DROP TABLE {name}")
                conn.commit()
            finally:
                conn.close()
        self.cfg.get("resources", {}).pop(name, None)
        self.saveConfig()
        self.reloadServer()
        return name

    def alterDBTable(self, table, field_attrs):
        print(f"Altering {table} with {field_attrs}")
        if self.sqlite:
            with sqlite3.connect(self.sqlite.sql_config["database"]) as db:
                fields = self.getSqliteTable(db, {"name": table})
                if field_attrs.get("drop"):
                    match = next(
                        (f for f in fields if f[0] == field_attrs["cid"]), None
                    )
                    if match is None:
                        raise ValueError(
                            f"No such column cid={field_attrs['cid']} on {table}"
                        )
                    (cid, name, datatype, notnull, dflt, pk) = match
                    if pk:
                        raise ValueError(f"Cannot drop primary key column '{name}'")
                    if len(fields) <= 1:
                        raise ValueError(
                            f"Cannot drop the only remaining column on '{table}'"
                        )
                    if sqlite3.sqlite_version_info < (3, 35, 0):
                        raise RuntimeError(
                            f"SQLite {sqlite3.sqlite_version} does not support "
                            "DROP COLUMN (requires >= 3.35.0)"
                        )
                    db.execute(f"ALTER TABLE {table} DROP COLUMN {name}")
                    db.commit()
                    self.reloadServer()
                    return
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
                        dflt = "''"
                    dflt = f"DEFAULT {dflt}" if dflt else ""
                    pk = "PRIMARY KEY" if pk == 1 else ""
                    sql = f"""ALTER TABLE {table}
                              ADD COLUMN {name} {datatype} {dflt} {notnull} {pk}"""
                    db.execute(sql)
                db.commit()
        elif self.sql and field_attrs.get("drop"):
            conn = pymysql.connect(
                host=self.sql.sql_config["host"],
                user=self.sql.sql_config["user"],
                password=self.sql.sql_config["password"],
                database=self.sql.sql_config["database"],
            )
            try:
                cur = conn.cursor()
                cur.execute(f"DESCRIBE {table}")
                fields = cur.fetchall()
                match = next(
                    (f for f in fields if f[0] == field_attrs["name"]), None
                )
                if match is None:
                    raise ValueError(
                        f"No such column '{field_attrs['name']}' on {table}"
                    )
                if match[3] == "PRI":
                    raise ValueError(f"Cannot drop primary key column '{match[0]}'")
                if len(fields) <= 1:
                    raise ValueError(
                        f"Cannot drop the only remaining column on '{table}'"
                    )
                cur.execute(f"ALTER TABLE {table} DROP COLUMN {match[0]}")
                conn.commit()
            finally:
                conn.close()
        self.reloadServer()

    def createResourceFile(self, name):
        name = name.strip().lower()
        if not resource_scaffold.NAME_RE.match(name):
            raise ValueError(f"Invalid resource name: {name}")
        resource_scaffold.writeResourceFile(
            os.path.join(os.getcwd(), "resources"), name
        )
        self.getResourceConfig(name)["paths"] = resource_scaffold.defaultPaths(name)
        self.saveConfig()
        self.reloadServer()
        return name

    def deleteResourceFile(self, name):
        resource_scaffold.deleteResourceFile(
            os.path.join(os.getcwd(), "resources"), name
        )
        self.cfg.get("resources", {}).pop(name, None)
        self.saveConfig()
        self.reloadServer()
        return name

    def getResourceConfig(self, resource: str) -> dict:
        return self.cfg.setdefault("resources", {}).setdefault(resource, {})

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

    def removePath(self, resource, index):
        print(f"Removing path for {resource}")
        cfg_resource = self.getResourceConfig(resource)
        if "paths" not in cfg_resource:
            cfg_resource["paths"] = []
        try:
            cfg_resource["paths"].pop(index)
        except IndexError:
            pass
        self.saveConfig()
        self.reloadServer()

    @staticmethod
    def _normalizeRoles(roles: Union[list, bool, str]) -> Union[list, bool]:
        if isinstance(roles, (list, bool)):
            return roles
        if roles.lower() in ["true", "false"]:
            return roles.lower() == "true"
        return roles.split(",")

    def _setRoles(
        self, resource: str, method: Union[str, list], roles: Union[list, bool, str]
    ):
        cfg_resource = self.getResourceConfig(resource)
        cfg_roles = cfg_resource.setdefault("roles", {})
        normalized = self._normalizeRoles(roles)
        for m in method if isinstance(method, list) else [method]:
            cfg_roles[m] = normalized

    def updateRoles(
        self, resource: str, method: Union[str, list], roles: Union[list, bool, str]
    ):
        print(f"Updating roles for {resource}")
        self._setRoles(resource, method, roles)
        self.saveConfig()
        self.reloadServer()

    def updateRolesBulk(self, updates: list) -> None:
        for u in updates:
            self._setRoles(u["resource"], u["method"], u["roles"])
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
