# Bottle and plugins
from bottle import Bottle, JSONPlugin, static_file
from .plugins import API, Resource, JWTPlugin, authFunc, sqlitePlugin, sqlPlugin, CorsPlugin

# Other imports
from typing import Union
import toml
import os
import re
import sys
import secrets
import inspect
import importlib
import pkgutil
import copy
from . import resource_factory, reload, resource_scaffold, openapi
from .resources import (
    AllResources,
    DataTypes,
    Config,
    PythonResources,
    ResourceRoles,
    SQLITE_TYPES,
    MYSQL_TYPES,
)
from .dashboard.resources.token import DashboardToken
import pymysql
import pymysql.cursors
import sqlite3
import json
import datetime
from decimal import Decimal
from pathlib import Path


DIST = f"{Path(__file__).parent.parent.resolve()}/bottler/dashboard/dist"

# Settings a mounted child app always takes from its parent (see
# setupMounts): one token, one CORS policy and one URL space for the whole
# process, whatever the child's own bottler.toml says.
MOUNT_INHERITED = ("jwt", "cors", "rest", "dashboard", "openapi", "api_prefix")

_MOUNT_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")

# Column DEFAULT values are concatenated directly into DDL (neither sqlite3
# nor pymysql support bind parameters inside ALTER TABLE), so only allow a
# safe literal shape: NULL/CURRENT_TIMESTAMP, a bare number, or a
# single-quoted string with escaped/absent embedded quotes.
_SAFE_DEFAULT_RE = re.compile(
    r"(?i)^(null|current_timestamp)$|^-?\d+(\.\d+)?$|^'(?:[^'\\]|'')*'$"
)


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


class Bottler(Bottle):
    def __init__(
        self,
        cors: Union[bool, dict] = True,
        rest: bool = True,
        jwt: Union[bool, str, dict] = True,
        api_prefix: str = "",
        default_roles: Union[bool, list, str] = False,
        sqlite: Union[bool, str, dict] = False,
        sql: Union[bool, str, dict] = False,
        gen_db: bool = True,
        gen_res: bool = True,
        gen_auth: bool = True,
        gen_hooks: bool = True,
        cfg_file: str = "bottler.toml",
        dashboard: bool = False,
        openapi: Union[bool, dict] = True,
        run_args: dict = {},
        package: str = None,
        base_dir: str = None,
        mounts: dict = None,
        mounted: bool = False,
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
        # Package mode: resources come from the installed package
        # `<package>.resources` instead of ./resources, and the package's
        # config lives in base_dir (its bottler.toml, plus whatever the
        # package itself reads from there via app.base_dir).
        self.package = package
        self.base_dir = os.path.abspath(base_dir) if base_dir else None
        self.mounted = mounted
        if self.base_dir and cfg_file == "bottler.toml":
            cfg_file = os.path.join(self.base_dir, "bottler.toml")
        self.cfg_file = cfg_file
        self.run_args = run_args
        try:
            self.cfg = toml.load(cfg_file)
        except (OSError, TypeError):
            # No usable file at cfg_file (missing, a directory, cfg_file=None,
            # ...) -- fall back to constructor args taking full effect.
            self.cfg = {}
        except toml.TomlDecodeError as e:
            # The file exists but isn't valid TOML -- this one's worth a
            # loud warning rather than silently discarding the user's config.
            print(f"Warning: failed to parse {cfg_file}: {e}")
            self.cfg = {}
        dashboard = self._cfgValue("dashboard", dashboard)
        cors = self._cfgValue("cors", cors)
        rest = self._cfgValue("rest", rest)
        jwt = self._cfgValue("jwt", jwt)
        sqlite = self._cfgValue("sqlite", sqlite)
        sql = self._cfgValue("sql", sql)
        openapi = self._cfgValue("openapi", openapi)
        api_prefix = self._cfgValue("api_prefix", api_prefix)
        # A mounted child never mounts anything itself -- one level only.
        mounts = None if mounted else self._cfgValue("mounts", mounts)
        api_prefix = (api_prefix or "").strip().strip("/")
        self.api_prefix = f"/{api_prefix}" if api_prefix else ""
        # Roles every hand-authored and DB-generated resource route requires
        # unless its class or resources.<name>.roles says otherwise (True =
        # any valid token, a list = at least one of those roles). False keeps
        # routes open by default. See setRoles().
        default_roles = self._cfgValue("default_roles", default_roles)
        self.default_roles = (
            self._normalizeRoles(default_roles) if default_roles else False
        )
        # Resources that override api_prefix (e.g. a root-mounted SPA/static-
        # file resource opting out via api_prefix="") are registered last,
        # after every default-prefixed route -- hand-authored, meta, and
        # DB auto-CRUD -- so a catch-all route like /<path:path> can never
        # shadow a real, more-specific API route based on registration order
        # (Bottle's router matches dynamic routes in registration order,
        # first match wins, not most-specific-match).
        self._deferred_resources = []
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
        self.setupMounts(mounts)
        self._registerDeferredResources()
        self.setupOpenApi(openapi)
        # Runs last, after every route above is registered, so hooks.py's
        # configure(app) can freely add routes/plugins/middleware or
        # override anything Bottler itself just set up.
        self.setupHooks(gen_hooks)

    def _cfgValue(self, key, value):
        """bottler.toml wins over the constructor arg -- except, in a
        mounted child, for the MOUNT_INHERITED keys its parent passed in."""
        if key in self.cfg and not (self.mounted and key in MOUNT_INHERITED):
            return self.cfg[key]
        return value

    @property
    def resource_names(self):
        try:
            return set([r.name for r in self.rest.resources])
        except:
            return set()

    def apiPath(self, path: str, prefix=None) -> str:
        """Prepend api_prefix (or an explicit per-resource override) to a
        route rule. `prefix=None` means "use self.api_prefix"; a Resource
        subclass can pass its own `api_prefix` class attribute (including
        "" to opt out of the global prefix entirely, e.g. a root-mounted
        SPA/static-file resource)."""
        prefix = self.api_prefix if prefix is None else prefix
        return f"{prefix}{path}" if prefix else path

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
                f"{missing_str} in {self.cfg_file} or pass to the Bottler "
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
        self._cors_cfg = cors
        if cors:
            origins = cors.get("origins") if isinstance(cors, dict) else None
            self.cors = CorsPlugin(origins=origins)
            self.install(self.cors)
        else:
            self.cors = None

    def setupRest(self, rest, gen: bool):
        if rest:
            self.rest = API()
            self.install(self.rest)
            if gen and self.package:
                self.importPackageResources()
            elif gen and os.path.exists(os.getcwd() + "/resources"):
                self.importResourcesDir()
            for name, resource, paths in (
                ("_resources", AllResources(self), ("/_resources", "/_resources/<resource>")),
                ("_datatypes", DataTypes(self), ("/_datatypes",)),
                ("bottler_cfg", Config(self), ("/bottler_cfg",)),
                (
                    "_python_resources",
                    PythonResources(self),
                    ("/_python_resources", "/_python_resources/<resource>"),
                ),
                ("_roles", ResourceRoles(self), ("/_roles",)),
            ):
                self._protectBuiltinResource(resource, name)
                self.rest.addResource(resource, *paths)
            if getattr(self, "dashboard_token", None):
                self.rest.addResource(self.dashboard_token, "/dashboard/setup")
        else:
            self.rest = None

    def _protectBuiltinResource(self, resource, name):
        # These meta/admin resources (schema mutation, full config dump/
        # replace, role editing) must never be reachable without a valid
        # token by default -- unlike hand-authored or DB-generated
        # resources, nothing else gates access to them. Unlike those,
        # AllResources/DataTypes/Config/PythonResources/ResourceRoles are
        # singleton classes imported once at module load rather than
        # recreated per Bottler() instantiation, so their route config
        # (stored as class attributes by Resource.setRouteConfig) is reset
        # to a clean slate first -- otherwise a later instantiation's toml
        # role config could be silently blocked by a bool leftover from an
        # earlier instantiation in the same process (tests, the CLI retry
        # loop). setRoles() is then free to apply any
        # resources.<name>.roles override cleanly, and only methods it left
        # untouched fall back to the "any authenticated user" default.
        # OPTIONS is left alone so CORS preflight still passes through.
        for meth in resource.Methods:
            resource.setRouteConfig(meth, {})
        self.setRoles(resource, name, use_default=False)
        for meth in resource.Methods:
            if meth == resource.Methods.OPTIONS:
                continue
            route_cfg = resource.getRouteConfig(meth)
            route_cfg.setdefault("roles", True)
            resource.setRouteConfig(meth, route_cfg)

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
            if jwt is True:
                # No explicit key given (constructor default / bare `jwt = true`
                # in bottler.toml) -- generate a random one rather than
                # falling back to a hardcoded, publicly-known secret. This key
                # is process-local and not persisted: it keeps every
                # unconfigured deployment from sharing the same guessable
                # secret, at the cost of invalidating outstanding tokens on
                # restart. Set `jwt` explicitly for a stable key.
                jwt = secrets.token_urlsafe(32)
                print(
                    "No JWT key configured -- using a randomly generated key "
                    "for this run. Tokens issued now will stop validating "
                    f"after a restart; set `jwt` explicitly (or in "
                    f"{self.cfg_file}) for a stable key."
                )
            if type(jwt) == str:
                cfg["jwt_key"] = jwt
            else:
                cfg = jwt
            self._jwt_cfg = cfg
            self.jwt = JWTPlugin(**cfg)
            self.install(self.jwt)
            if self.mounted:
                # Only the parent issues tokens. Clearing token_paths also
                # stops any child route that flattens to "token" from turning
                # into a token endpoint (JWTPlugin.apply keys off route.rule).
                self.jwt.token_paths = {}
                return
            # Create default token callbacks. JWTPlugin.apply() looks up the
            # request's token path by flattening route.rule ("/" stripped),
            # so if api_prefix moves "/token" to e.g. "/api/token", the
            # token_paths dict key has to be rekeyed to "apitoken" to match,
            # or the endpoint silently stops issuing tokens.
            for path, callback in list(self.jwt.token_paths.items()):
                rule = self.apiPath("/" + path)
                key = rule.replace("/", "")
                if key != path:
                    self.jwt.token_paths[key] = self.jwt.token_paths.pop(path)
                self._default_token_key = key
                self.route(rule, "GET", callback)
                self.route(rule, "POST", callback)
                self.route(rule, "OPTIONS", callback)
                self.route(
                    self.apiPath("/users/current"),
                    ["OPTIONS", "GET"],
                    lambda: {"user": "default"},
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

    def setTokenAuthFunction(self, func=None, token_path=None):
        if not func:
            func = authFunc
        if token_path is None:
            # Match whatever key setupJwt() actually rekeyed the default
            # token path to (e.g. "apitoken" when api_prefix is set) rather
            # than a bare "token" literal, or this would silently create a
            # second, unroutable dict entry instead of replacing the real one.
            token_path = getattr(self, "_default_token_key", "token") or "token"
        self.jwt.token_paths[token_path] = func

    def setupAuth(self, gen: bool):
        if self.package:
            # A package never brings its own login: the app that mounts it
            # (or its standalone host project) owns /token.
            return
        if not (gen and self.jwt and os.path.exists(os.path.join(os.getcwd(), "auth.py"))):
            return
        # Same temp-sys.path/sys.modules dance as importResourcesDir, scaled
        # down to a single top-level module instead of a package, so repeated
        # Bottler() construction against different project dirs in the
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

    def setupHooks(self, gen: bool):
        if self.package:
            if gen:
                self._runPackageHook()
            return
        if not (gen and os.path.exists(os.path.join(os.getcwd(), "hooks.py"))):
            return
        # Same temp-sys.path/sys.modules dance as setupAuth/importResourcesDir,
        # scaled down to a single top-level module, so repeated Bottler()
        # construction against different project dirs in the same process
        # never serves a stale cached hooks module.
        project_root = os.getcwd()
        path_added = project_root not in sys.path
        if path_added:
            sys.path.insert(0, project_root)
        try:
            module = importlib.import_module("hooks")
        finally:
            if "hooks" in sys.modules:
                del sys.modules["hooks"]
            if path_added:
                sys.path.remove(project_root)
        func = getattr(module, "configure", None)
        if not callable(func):
            print("hooks.py found but has no callable 'configure' -- skipping")
            return
        func(self)

    def importResourcesDir(self):
        # Load resources/ as a real (namespace) package rather than
        # exec'ing each file in isolation, so resource files can use
        # relative imports (from . import helper) or import other modules
        # elsewhere in the project. The project root and cached
        # resources/resources.* modules are cleaned up afterwards so that
        # repeated Bottler() instantiations against different projects
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

    def _runPackageHook(self):
        # The package's own `configure(app)` (in its __init__), if any --
        # package mode's equivalent of hooks.py. Runs last, like hooks.py;
        # app.base_dir tells the package where its config lives.
        func = getattr(importlib.import_module(self.package), "configure", None)
        if callable(func):
            func(self)

    def importPackageResources(self):
        # An installed package stays cached in sys.modules (unlike
        # ./resources, which importResourcesDir purges), so its classes are
        # reused by every Bottler built in this process -- see
        # _resetRouteConfig for what that means for roles.
        package = f"{self.package}.resources"
        module = importlib.import_module(package)
        for info in sorted(pkgutil.iter_modules(module.__path__), key=lambda i: i.name):
            self.importResourcesFromFile(f"{info.name}.py", package=package)

    def _resetRouteConfig(self, resource):
        # setRoles() mutates class-level route config (and appends toml roles
        # with +=), so a cached package class would pile up roles on every
        # build. Snapshot the class's own config the first time it's seen and
        # restore it before each setRoles() instead.
        if "_bottler_route_cfg" not in resource.__dict__:
            resource._bottler_route_cfg = {
                meth: copy.deepcopy(resource.getRouteConfig(meth)) for meth in resource.Methods
            }
        for meth, cfg in resource._bottler_route_cfg.items():
            resource.setRouteConfig(meth, copy.deepcopy(cfg))

    def importResourcesFromFile(self, py_file, package="resources"):
        module_name = py_file[:-3]
        if module_name == "__init__" or py_file[-3:] != ".py":
            return
        module = importlib.import_module(f"{package}.{module_name}")
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
            paths = [self.apiPath(p, prefix=resource.api_prefix) for p in paths]
            if package != "resources":
                self._resetRouteConfig(resource)
            self.setRoles(resource, module_name)
            if resource.api_prefix is not None:
                # An explicit per-resource override -- defer to
                # _registerDeferredResources() so it can never shadow a
                # default-prefixed dynamic route based on os.listdir()'s
                # unspecified ordering (see api_prefix's design notes above).
                self._deferred_resources.append((cls[1], paths))
            else:
                self.rest.addResource(cls[1], *paths)

    def setupMounts(self, mounts):
        """Mount each `[mounts.<name>]` package as its own child Bottler
        at <api_prefix>/<name>/. Each child has its own sql/sqlite, resources,
        roles and DB auto-CRUD -- the one-database limit is per app, and
        Bottle runs a mounted route with its own app's plugins (the child's
        SQL plugin, so its own `db`). The child takes jwt/cors/api_prefix
        from this app, so one token works everywhere and only this app
        issues it.

        Each entry is a package name, or a table with `package` and
        `base_dir` (that package's config folder, default <name>; relative
        paths resolve against this app's bottler.toml folder)."""
        self.mounts = {}
        if not mounts:
            return
        if not self.rest:
            raise Exception("mounts require rest to be enabled")
        cfg_dir = (
            os.path.dirname(os.path.abspath(self.cfg_file))
            if isinstance(self.cfg_file, str)
            else os.getcwd()
        )
        for name, entry in mounts.items():
            if not _MOUNT_NAME_RE.match(name):
                raise Exception(f"Invalid mount name '{name}'")
            if isinstance(entry, str):
                entry = {"package": entry}
            base_dir = os.path.join(cfg_dir, entry.get("base_dir", name))
            child = Bottler(
                package=entry["package"],
                base_dir=base_dir,
                mounted=True,
                cors=self._cors_cfg,
                jwt=dict(self._jwt_cfg) if self.jwt else False,
                default_roles=self.default_roles,
                api_prefix="",
                dashboard=False,
                openapi=False,
            )
            # The trailing "/" makes Bottle merge the child's routes into
            # this router (keeping route.app = child) instead of falling back
            # to an opaque WSGI mount.
            self.mount(self.apiPath(f"/{name}/"), child)
            self.mounts[name] = child

    def _registerDeferredResources(self):
        for resource, paths in self._deferred_resources:
            self.rest.addResource(resource, *paths)

    def setRoles(self, resource, name, use_default=True):
        # Precedence: roles declared on the class > resources.<name>.roles >
        # default_roles. An explicit `false` in resources.<name>.roles still
        # counts as declared, so it opts that method out of default_roles.
        # OPTIONS never gets the default, so CORS preflight passes through.
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
            if (
                use_default
                and self.default_roles
                and meth != resource.Methods.OPTIONS
                and "roles" not in route_cfg
            ):
                default = self.default_roles
                route_cfg["roles"] = list(default) if isinstance(default, list) else default
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
            base_path = self.apiPath(f"/{table}")
            if base_path not in rules:
                endpoints = [base_path]
            keyed_path = self.apiPath(f"/{table}/<key>")
            if resource.key and keyed_path not in rules:
                endpoints.append(keyed_path)
            # Generic nested-ref route: resource_factory's get() resolves
            # the actual FK relationship (if any) at request time via
            # getRefs, so this single rule covers every table without
            # needing a per-relationship route generated ahead of time.
            nested_path = self.apiPath(f"/<ref_table>/<ref_id>/{table}")
            if nested_path not in rules:
                endpoints.append(nested_path)
            try:
                for path in self.cfg["resources"][table]["paths"]:
                    path = self.apiPath(path)
                    if path not in rules:
                        endpoints.append(path)
            except KeyError:
                pass
            if endpoints:
                self.rest.addResource(resource, endpoints)

    def _connect(self, dictrows=True):
        # Shared sqlite3/pymysql connection construction -- was duplicated
        # (with the same dict-row-factory/DictCursor setup) across
        # getDBCursor, getDBTables, dropTable, and alterDBTable.
        if self.sqlite:
            # Every current caller wants dict rows from sqlite -- dictrows
            # only ever matters for the pymysql side below.
            conn = sqlite3.connect(self.sqlite.sql_config["database"])
            conn.row_factory = lambda cursor, row: {
                col[0]: row[idx] for idx, col in enumerate(cursor.description)
            }
        elif self.sql:
            cfg = dict(
                host=self.sql.sql_config["host"],
                user=self.sql.sql_config["user"],
                password=self.sql.sql_config["password"],
                database=self.sql.sql_config["database"],
            )
            if dictrows:
                cfg["cursorclass"] = pymysql.cursors.DictCursor
            conn = pymysql.connect(**cfg)
        else:
            raise Exception("No database configured (sql or sqlite)")
        return conn

    def getDBCursor(self) -> Union[pymysql.cursors.Cursor, sqlite3.Cursor]:
        conn = self._connect()
        db = conn.cursor()
        return db

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
        conn = self._connect()
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
                db.execute(sql)
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
            conn = self._connect(dictrows=False)
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

    def _validateIdentifier(self, value, what="identifier"):
        if not value or not resource_scaffold.NAME_RE.match(value):
            raise ValueError(f"Invalid {what}: {value}")

    def _validateDatatype(self, datatype):
        if not datatype:
            return
        allowed = SQLITE_TYPES if self.sqlite else MYSQL_TYPES
        if datatype.strip().upper() not in allowed:
            raise ValueError(f"Invalid column type: {datatype}")

    def _validateDefaultValue(self, dflt):
        if dflt is None or dflt == "":
            return
        if not _SAFE_DEFAULT_RE.match(str(dflt)):
            raise ValueError(f"Invalid default value: {dflt}")

    def alterDBTable(self, table, field_attrs):
        print(f"Altering {table} with {field_attrs}")
        self._validateIdentifier(table, "table name")
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
                    # name comes from the DB's own introspected schema, not
                    # request input, but validate anyway for defense in depth.
                    self._validateIdentifier(name, "column name")
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
                if cid or cid == 0:
                    self._validateIdentifier(name, "column name")
                    self._validateIdentifier(field_attrs["name"], "column name")
                    sql = f"""ALTER TABLE {table}
                              RENAME COLUMN {name} TO {field_attrs['name']}"""
                    db.execute(sql)
                elif name:
                    self._validateIdentifier(name, "column name")
                    self._validateDatatype(datatype)
                    self._validateDefaultValue(dflt)
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
        elif self.sql:
            conn = self._connect(dictrows=False)
            try:
                cur = conn.cursor()
                cur.execute(f"DESCRIBE {table}")
                fields = cur.fetchall()
                if field_attrs.get("drop"):
                    match = next(
                        (f for f in fields if f[0] == field_attrs["name"]), None
                    )
                    if match is None:
                        raise ValueError(
                            f"No such column '{field_attrs['name']}' on {table}"
                        )
                    if match[3] == "PRI":
                        raise ValueError(
                            f"Cannot drop primary key column '{match[0]}'"
                        )
                    if len(fields) <= 1:
                        raise ValueError(
                            f"Cannot drop the only remaining column on '{table}'"
                        )
                    self._validateIdentifier(match[0], "column name")
                    cur.execute(f"ALTER TABLE {table} DROP COLUMN {match[0]}")
                    conn.commit()
                else:
                    name = field_attrs.get("name")
                    # MySQL's DESCRIBE has no sqlite-style numeric "cid" --
                    # reuse the same key to carry the existing column's
                    # current name instead, so a truthy `cid` still means
                    # "rename this column" and a falsy one means "add".
                    old_name = field_attrs.get("cid")
                    match = (
                        next((f for f in fields if f[0] == old_name), None)
                        if old_name
                        else None
                    )
                    if match:
                        self._validateIdentifier(old_name, "column name")
                        self._validateIdentifier(name, "column name")
                        # RENAME COLUMN requires MySQL >= 8.0 / MariaDB >= 10.5.2.
                        cur.execute(
                            f"ALTER TABLE {table} RENAME COLUMN {old_name} TO {name}"
                        )
                    elif name:
                        datatype = field_attrs.get("type")
                        dflt = field_attrs.get("dflt_value")
                        notnull = field_attrs.get("notnull")
                        pk = field_attrs.get("pk")
                        self._validateIdentifier(name, "column name")
                        self._validateDatatype(datatype)
                        self._validateDefaultValue(dflt)
                        datatype = datatype or "TEXT"
                        notnull_sql = "NOT NULL" if notnull else ""
                        if notnull and not dflt:
                            dflt = "''"
                        dflt_sql = f"DEFAULT {dflt}" if dflt else ""
                        pk_sql = "PRIMARY KEY" if pk == 1 else ""
                        cur.execute(
                            f"ALTER TABLE {table} ADD COLUMN {name} {datatype} "
                            f"{dflt_sql} {notnull_sql} {pk_sql}"
                        )
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
        self._validateIdentifier(name, "resource name")
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
