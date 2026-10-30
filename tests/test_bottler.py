import _paths  # noqa: F401
import unittest
from unittest import mock
import webtest
import datetime
import decimal
import pymysql
from bottler import Bottler
from bottler.core import JSONEncoder
from bottler.plugins import rest as bottle_rest
from bottler.plugins import jwt as bottle_jwt
import toml
import os
import sys
import shutil
import tempfile
import sqlite3
import db_fixtures
from mysql_mock import make_mysql_cursor, patch_pymysql_connect, pragma_raises_side_effect

DEBUG = False
NONEXISTENT_CFG = "no_such_bottler_cfg.toml"


class TestResource(bottle_rest.Resource):
    def options(self):
        pass

    def get(self):
        return {}

    def post(self):
        return self.get()

    def put(self):
        return self.get()

    def patch(self):
        return self.get()

    def delete(self):
        pass


class TestBottler(unittest.TestCase):
    def setUp(self) -> None:
        self.bottler = Bottler(gen_res=False, gen_db=False)
        self.app = webtest.TestApp(self.bottler)

    def addTestResource(self):
        self.bottler.rest.addResource(TestResource, "/test_resource")

    def _writeCfg(self, content):
        fd, path = tempfile.mkstemp(suffix=".toml", dir=os.getcwd())
        os.close(fd)
        with open(path, "w") as f:
            f.write(content)
        self.addCleanup(os.remove, path)
        return path

    def test_init(self):
        self.assertIsNotNone(self.bottler.cors)
        self.assertIsNotNone(self.bottler.rest)
        self.assertIsInstance(self.bottler.jwt, bottle_jwt.JWTPlugin)
        self.assertIsNotNone(self.bottler.sqlite)

    # Config
    def test_loadConfig(self):
        cfg = toml.load("bottler.toml")
        self.assertEqual(cfg, self.bottler.cfg)

    def test_loadConfig_malformedToml_warnsAndFallsBackToEmpty(self):
        fd, path = tempfile.mkstemp(suffix=".toml", dir=os.getcwd())
        os.close(fd)
        self.addCleanup(os.remove, path)
        with open(path, "w") as f:
            f.write("not: valid: toml: [")
        bs = Bottler(
            cfg_file=path, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        self.assertEqual(bs.cfg, {})

    # REST
    def test_initRest_noDashboard_noMetaResources(self):
        self.assertNotIn("AllResources", self.bottler.resource_names)
        self.assertNotIn("DataTypes", self.bottler.resource_names)

    def test_initRest_dashboard_addsMetaResources(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, dashboard=True, jwt="k", sqlite=False,
            gen_res=False, gen_db=False,
        )
        self.assertIn("AllResources", bs.resource_names)
        self.assertIn("DataTypes", bs.resource_names)

    def test_initNoRest(self):
        self.bottler = Bottler(rest=False)
        self.assertIsNone(
            next((p for p in self.bottler.plugins if "API" in str(p)), None)
        )

    def test_addResource(self):
        self.addTestResource()
        self.assertIn("TestResource", self.bottler.resource_names)
        self.assertEqual(200, self.app.get("/test_resource").status_code)

    def test_restMethods(self):
        self.addTestResource()
        self.assertEqual(self.app.options("/test_resource").status_code, 200)
        self.assertEqual(self.app.get("/test_resource").status_code, 200)
        self.assertEqual(self.app.post("/test_resource").status_code, 200)
        self.assertEqual(self.app.put("/test_resource").status_code, 200)
        self.assertEqual(self.app.patch("/test_resource").status_code, 200)
        self.assertEqual(self.app.delete("/test_resource").status_code, 200)

    def test_genFileResource(self):
        self.bottler = Bottler(gen_res=True, gen_db=False)
        self.app = webtest.TestApp(self.bottler)
        self.assertIn("FileResource", self.bottler.resource_names)
        self.assertEqual(200, self.app.get("/file_resource").status_code)

    def test_genFileResource_relativeImport(self):
        # resources/relative_import_resource.py does `from . import _shared`
        # -- only works because resources/ is loaded as a real package.
        self.bottler = Bottler(gen_res=True, gen_db=False)
        self.app = webtest.TestApp(self.bottler)
        self.assertIn("RelativeImportResource", self.bottler.resource_names)
        resp = self.app.get("/relative_import_resource")
        self.assertEqual(200, resp.status_code)
        self.assertEqual("hello from _shared", resp.json["greeting"])

    def test_genFileResource_absoluteProjectImport(self):
        # resources/absolute_import_resource.py does
        # `from project_util import PROJECT_GREETING`, a module living at
        # the project root (tests/) rather than inside resources/.
        self.bottler = Bottler(gen_res=True, gen_db=False)
        self.app = webtest.TestApp(self.bottler)
        self.assertIn("AbsoluteImportResource", self.bottler.resource_names)
        resp = self.app.get("/absolute_import_resource")
        self.assertEqual(200, resp.status_code)
        self.assertEqual("hello from project_util", resp.json["greeting"])

    # JWT
    def test_initJWT(self):
        self.assertIsInstance(self.bottler.jwt, bottle_jwt.JWTPlugin)

    def test_initNoJWT(self):
        self.bottler = Bottler(jwt=False, cfg_file=None)
        self.assertIsNone(
            next((p for p in self.bottler.plugins if "JWT" in str(p)), None)
        )

    # SQL
    def test_initSQLite(self):
        self.assertIsNotNone(self.bottler.sqlite)

    def test_initNoSQLite(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG,
            sqlite=False,
            sql=False,
            jwt=False,
            gen_res=False,
            gen_db=False,
        )
        self.assertIsNone(bs.sqlite)

    def test_setupSql_dictConfig(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG,
            sql={"host": "h", "user": "u", "password": "p", "database": "d"},
            sqlite=False,
            jwt=False,
            gen_res=False,
            gen_db=False,
        )
        self.assertEqual(bs.sql.sql_config["database"], "d")

    def test_setupSql_strConfig(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG,
            sql="dbname",
            sqlite=False,
            jwt=False,
            gen_res=False,
            gen_db=False,
        )
        self.assertEqual(bs.sql.sql_config["database"], "dbname")

    def test_setupSqlite_dictConfig(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG,
            sqlite={"database": tmp_db},
            sql=False,
            jwt=False,
            gen_res=False,
            gen_db=False,
        )
        self.assertEqual(bs.sqlite.sql_config["database"], tmp_db)

    def test_setupJwt_boolTrue_generatesRandomKey(self):
        # jwt=True (the constructor default) means "enabled, no explicit key"
        # -- a random per-process secret is generated instead of falling
        # back to a hardcoded, guessable one.
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, jwt=True, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        self.assertIsInstance(bs.jwt.jwt_key, str)
        self.assertNotEqual(bs.jwt.jwt_key, "default")
        self.assertGreater(len(bs.jwt.jwt_key), 16)

    def test_setupJwt_boolTrue_eachInstantiationGetsDifferentKey(self):
        bs1 = Bottler(
            cfg_file=NONEXISTENT_CFG, jwt=True, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs2 = Bottler(
            cfg_file=NONEXISTENT_CFG, jwt=True, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        self.assertNotEqual(bs1.jwt.jwt_key, bs2.jwt.jwt_key)

    def test_setupSqlite_neitherStrNorDict_stillCallsFactory(self):
        # sqlite=True (bool) skips both branches; sqlitePlugin's required
        # `database` positional arg then crashes.
        with self.assertRaises(TypeError):
            Bottler(
                cfg_file=NONEXISTENT_CFG, sqlite=True, sql=False, jwt=False,
                gen_res=False, gen_db=False,
            )

    def test_setTokenAuthFunction_defaultsToAuthFunc(self):
        from bottler.plugins.jwt import authFunc

        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, jwt="k", sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.setTokenAuthFunction()
        self.assertIs(bs.jwt.token_paths["token"], authFunc)

    def test_setTokenAuthFunction_customFunc(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, jwt="k", sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        custom = lambda: {"exp": 123}
        bs.setTokenAuthFunction(custom)
        self.assertIs(bs.jwt.token_paths["token"], custom)

    # --- api_prefix / apiPath ---
    def test_apiPath_defaultNoPrefix_returnsPathUnchanged(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        self.assertEqual(bs.api_prefix, "")
        self.assertEqual(bs.apiPath("/reports"), "/reports")

    def test_apiPath_globalPrefix_prepended(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, api_prefix="/api", jwt=False,
            sqlite=False, sql=False, gen_res=False, gen_db=False,
        )
        self.assertEqual(bs.apiPath("/reports"), "/api/reports")

    def test_apiPath_explicitEmptyOverride_bypassesGlobalPrefix(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, api_prefix="/api", jwt=False,
            sqlite=False, sql=False, gen_res=False, gen_db=False,
        )
        self.assertEqual(bs.apiPath("/", prefix=""), "/")

    def test_apiPath_normalizesSurroundingSlashesAndWhitespace(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, api_prefix=" /api/ ", jwt=False,
            sqlite=False, sql=False, gen_res=False, gen_db=False,
        )
        self.assertEqual(bs.api_prefix, "/api")

    def test_apiPath_emptyStringPrefix_normalizesToOff(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, api_prefix="", jwt=False,
            sqlite=False, sql=False, gen_res=False, gen_db=False,
        )
        self.assertEqual(bs.api_prefix, "")

    def test_configPrecedence_apiPrefix_tomlOverridesCtor(self):
        path = self._writeCfg('api_prefix = "/api"\n')
        bs = Bottler(
            cfg_file=path, api_prefix="", jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        self.assertEqual(bs.api_prefix, "/api")

    def test_setupJwt_apiPrefix_rekeysTokenPathAndRoutesUnderPrefix(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, api_prefix="/api", jwt="k",
            sqlite=False, sql=False, gen_res=False, gen_db=False,
        )
        self.assertNotIn("token", bs.jwt.token_paths)
        self.assertIn("apitoken", bs.jwt.token_paths)
        app = webtest.TestApp(bs)
        resp = app.post_json("/api/token", {})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("token", resp.json)
        self.assertEqual(app.get("/token", expect_errors=True).status_code, 404)
        self.assertEqual(
            app.get("/api/users/current").json, {"user": "default"}
        )

    def test_setTokenAuthFunction_explicitTokenPath_bypassesDefaultLookup(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, jwt="k", sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        custom = lambda: {"exp": 123}
        bs.setTokenAuthFunction(custom, token_path="othertoken")
        self.assertIs(bs.jwt.token_paths["othertoken"], custom)
        self.assertIn("token", bs.jwt.token_paths)

    def test_setTokenAuthFunction_apiPrefix_defaultsToRekeyedPath(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, api_prefix="/api", jwt="k",
            sqlite=False, sql=False, gen_res=False, gen_db=False,
        )
        custom = lambda: {"exp": 123}
        bs.setTokenAuthFunction(custom)
        self.assertIs(bs.jwt.token_paths["apitoken"], custom)
        self.assertNotIn("token", bs.jwt.token_paths)

    # --- setupAuth: auth.py:authenticate auto-discovery ---
    def _writeAuthPy(self, tmp, body="def authenticate(**kwargs):\n    return {'user': 'x'}\n"):
        with open(os.path.join(tmp, "auth.py"), "w") as f:
            f.write(body)

    def test_setupAuth_authPyPresent_wiresUp(self):
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            self._writeAuthPy(tmp)
            bs = Bottler(
                cfg_file=NONEXISTENT_CFG, jwt="k", sqlite=False, sql=False,
                gen_res=False, gen_db=False,
            )
            self.assertEqual(bs.jwt.token_paths["token"](), {"user": "x"})
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp)

    def test_setupAuth_noAuthPy_noop(self):
        from bottler.plugins.jwt import authFunc

        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            bs = Bottler(
                cfg_file=NONEXISTENT_CFG, jwt="k", sqlite=False, sql=False,
                gen_res=False, gen_db=False,
            )
            self.assertIs(bs.jwt.token_paths["token"], authFunc)
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp)

    def test_setupAuth_genAuthFalse_noop(self):
        from bottler.plugins.jwt import authFunc

        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            self._writeAuthPy(tmp)
            bs = Bottler(
                cfg_file=NONEXISTENT_CFG, jwt="k", sqlite=False, sql=False,
                gen_res=False, gen_db=False, gen_auth=False,
            )
            self.assertIs(bs.jwt.token_paths["token"], authFunc)
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp)

    def test_setupAuth_jwtDisabled_noop(self):
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            self._writeAuthPy(tmp)
            bs = Bottler(
                cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
                gen_res=False, gen_db=False,
            )
            self.assertIsNone(bs.jwt)
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp)

    def test_setupAuth_missingAuthenticateAttr_warnsAndSkips(self):
        from bottler.plugins.jwt import authFunc

        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            self._writeAuthPy(tmp, body="x = 1\n")
            with mock.patch("builtins.print") as mock_print:
                bs = Bottler(
                    cfg_file=NONEXISTENT_CFG, jwt="k", sqlite=False, sql=False,
                    gen_res=False, gen_db=False,
                )
            self.assertIs(bs.jwt.token_paths["token"], authFunc)
            self.assertTrue(
                any("authenticate" in str(c.args) for c in mock_print.call_args_list)
            )
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp)

    def test_setupAuth_authenticateNotCallable_warnsAndSkips(self):
        from bottler.plugins.jwt import authFunc

        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            self._writeAuthPy(tmp, body="authenticate = 'not callable'\n")
            bs = Bottler(
                cfg_file=NONEXISTENT_CFG, jwt="k", sqlite=False, sql=False,
                gen_res=False, gen_db=False,
            )
            self.assertIs(bs.jwt.token_paths["token"], authFunc)
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp)

    def test_setupAuth_repeatedConstructionAcrossProjects_noStaleModule(self):
        cwd = os.getcwd()
        tmp1 = tempfile.mkdtemp()
        tmp2 = tempfile.mkdtemp()
        try:
            os.chdir(tmp1)
            self._writeAuthPy(
                tmp1, body="def authenticate(**kwargs):\n    return {'user': 'one'}\n"
            )
            bs1 = Bottler(
                cfg_file=NONEXISTENT_CFG, jwt="k", sqlite=False, sql=False,
                gen_res=False, gen_db=False,
            )
            self.assertEqual(bs1.jwt.token_paths["token"](), {"user": "one"})
            self.assertNotIn("auth", sys.modules)

            os.chdir(tmp2)
            self._writeAuthPy(
                tmp2, body="def authenticate(**kwargs):\n    return {'user': 'two'}\n"
            )
            bs2 = Bottler(
                cfg_file=NONEXISTENT_CFG, jwt="k", sqlite=False, sql=False,
                gen_res=False, gen_db=False,
            )
            self.assertEqual(bs2.jwt.token_paths["token"](), {"user": "two"})
            self.assertNotIn("auth", sys.modules)
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp1)
            shutil.rmtree(tmp2)

    def test_setupAuth_projectRootAlreadyOnSysPath_notRemoved(self):
        # When project_root is already on sys.path (e.g. left there by
        # something else), setupAuth must neither re-add nor remove it --
        # only clean up what it itself added.
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            self._writeAuthPy(tmp)
            sys.path.insert(0, tmp)
            try:
                bs = Bottler(
                    cfg_file=NONEXISTENT_CFG, jwt="k", sqlite=False, sql=False,
                    gen_res=False, gen_db=False,
                )
                self.assertEqual(bs.jwt.token_paths["token"](), {"user": "x"})
                self.assertIn(tmp, sys.path)
            finally:
                sys.path.remove(tmp)
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp)

    def test_setupAuth_authPyBroken_raisesAndSkipsModuleCleanup(self):
        # A syntax error in auth.py means import_module() never adds "auth"
        # to sys.modules -- the cleanup's "if 'auth' in sys.modules" guard
        # must not choke on that, and the original exception must propagate.
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            self._writeAuthPy(tmp, body="def authenticate(:\n    pass\n")
            with self.assertRaises(SyntaxError):
                Bottler(
                    cfg_file=NONEXISTENT_CFG, jwt="k", sqlite=False, sql=False,
                    gen_res=False, gen_db=False,
                )
            self.assertNotIn("auth", sys.modules)
            self.assertNotIn(tmp, sys.path)
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp)

    # --- setupHooks: hooks.py:configure auto-discovery ---
    def _writeHooksPy(self, tmp, body="def configure(app):\n    app.hook_ran = True\n"):
        with open(os.path.join(tmp, "hooks.py"), "w") as f:
            f.write(body)

    def test_setupHooks_hooksPyPresent_wiresUp(self):
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            self._writeHooksPy(tmp)
            bs = Bottler(
                cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
                gen_res=False, gen_db=False,
            )
            self.assertTrue(bs.hook_ran)
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp)

    def test_setupHooks_noHooksPy_noop(self):
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            bs = Bottler(
                cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
                gen_res=False, gen_db=False,
            )
            self.assertFalse(hasattr(bs, "hook_ran"))
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp)

    def test_setupHooks_genHooksFalse_noop(self):
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            self._writeHooksPy(tmp)
            bs = Bottler(
                cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
                gen_res=False, gen_db=False, gen_hooks=False,
            )
            self.assertFalse(hasattr(bs, "hook_ran"))
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp)

    def test_setupHooks_missingConfigureAttr_warnsAndSkips(self):
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            self._writeHooksPy(tmp, body="x = 1\n")
            with mock.patch("builtins.print") as mock_print:
                bs = Bottler(
                    cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
                    gen_res=False, gen_db=False,
                )
            self.assertFalse(hasattr(bs, "hook_ran"))
            self.assertTrue(
                any("configure" in str(c.args) for c in mock_print.call_args_list)
            )
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp)

    def test_setupHooks_configureNotCallable_warnsAndSkips(self):
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            self._writeHooksPy(tmp, body="configure = 'not callable'\n")
            bs = Bottler(
                cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
                gen_res=False, gen_db=False,
            )
            self.assertFalse(hasattr(bs, "hook_ran"))
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp)

    def test_setupHooks_repeatedConstructionAcrossProjects_noStaleModule(self):
        cwd = os.getcwd()
        tmp1 = tempfile.mkdtemp()
        tmp2 = tempfile.mkdtemp()
        try:
            os.chdir(tmp1)
            self._writeHooksPy(
                tmp1, body="def configure(app):\n    app.hook_ran = 'one'\n"
            )
            bs1 = Bottler(
                cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
                gen_res=False, gen_db=False,
            )
            self.assertEqual(bs1.hook_ran, "one")
            self.assertNotIn("hooks", sys.modules)

            os.chdir(tmp2)
            self._writeHooksPy(
                tmp2, body="def configure(app):\n    app.hook_ran = 'two'\n"
            )
            bs2 = Bottler(
                cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
                gen_res=False, gen_db=False,
            )
            self.assertEqual(bs2.hook_ran, "two")
            self.assertNotIn("hooks", sys.modules)
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp1)
            shutil.rmtree(tmp2)

    def test_setupHooks_projectRootAlreadyOnSysPath_notRemoved(self):
        # When project_root is already on sys.path (e.g. left there by
        # something else), setupHooks must neither re-add nor remove it --
        # only clean up what it itself added.
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            self._writeHooksPy(tmp)
            sys.path.insert(0, tmp)
            try:
                bs = Bottler(
                    cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
                    gen_res=False, gen_db=False,
                )
                self.assertTrue(bs.hook_ran)
                self.assertIn(tmp, sys.path)
            finally:
                sys.path.remove(tmp)
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp)

    def test_setupHooks_hooksPyBroken_raisesAndSkipsModuleCleanup(self):
        # A syntax error in hooks.py means import_module() never adds
        # "hooks" to sys.modules -- the cleanup's "if 'hooks' in
        # sys.modules" guard must not choke on that, and the original
        # exception must propagate.
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            self._writeHooksPy(tmp, body="def configure(:\n    pass\n")
            with self.assertRaises(SyntaxError):
                Bottler(
                    cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
                    gen_res=False, gen_db=False,
                )
            self.assertNotIn("hooks", sys.modules)
            self.assertNotIn(tmp, sys.path)
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp)

    def test_setupJwt_strConfig(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG,
            jwt="mykey",
            sqlite=False,
            sql=False,
            gen_res=False,
            gen_db=False,
        )
        self.assertEqual(bs.jwt.jwt_key, "mykey")

    def test_setupCors_false_noPlugin(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG,
            cors=False,
            jwt=False,
            sqlite=False,
            sql=False,
            gen_res=False,
            gen_db=False,
        )
        self.assertIsNone(bs.cors)

    # --- config precedence: toml always overrides constructor args ---
    def test_configPrecedence_cors_tomlOverridesCtorFalse(self):
        path = self._writeCfg("cors = true\n")
        bs = Bottler(
            cfg_file=path, cors=False, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        self.assertIsNotNone(bs.cors)

    def test_configPrecedence_cors_tomlOverridesCtorTrue(self):
        path = self._writeCfg("cors = false\n")
        bs = Bottler(
            cfg_file=path, cors=True, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        self.assertIsNone(bs.cors)

    def test_configPrecedence_rest_tomlOverridesCtor(self):
        path = self._writeCfg("rest = false\n")
        bs = Bottler(
            cfg_file=path, rest=True, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        self.assertIsNone(bs.rest)

    def test_configPrecedence_jwt_tomlOverridesCtor(self):
        path = self._writeCfg("jwt = false\n")
        bs = Bottler(
            cfg_file=path, jwt="somekey", sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        self.assertIsNone(bs.jwt)

    def test_configPrecedence_sqlite_tomlOverridesCtor(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        path = self._writeCfg(f'sqlite = "{tmp_db}"\n')
        bs = Bottler(
            cfg_file=path, sqlite=False, sql=False, jwt=False,
            gen_res=False, gen_db=False,
        )
        self.assertIsNotNone(bs.sqlite)

    def test_configPrecedence_sql_tomlOverridesCtor(self):
        path = self._writeCfg(
            'sql = {host = "h", user = "u", password = "p", database = "d"}\n'
        )
        bs = Bottler(
            cfg_file=path, sql=False, sqlite=False, jwt=False,
            gen_res=False, gen_db=False,
        )
        self.assertIsNotNone(bs.sql)

    def test_configPrecedence_dashboard_tomlOverridesCtor(self):
        path = self._writeCfg("dashboard = true\n")
        bs = Bottler(
            cfg_file=path, dashboard=False, jwt="k", sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        self.assertTrue(any(r.rule.startswith("/dashboard") for r in bs.routes))

    # --- sql/sqlite mutual exclusion boundary ---
    def test_sqlAndSqliteBothTruthy_raises(self):
        with self.assertRaises(Exception):
            Bottler(
                cfg_file=NONEXISTENT_CFG, sql=True, sqlite=True, jwt=False,
                gen_res=False, gen_db=False,
            )

    def test_sqlAndSqliteBothFalsyEmpty_noRaise(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sql="", sqlite={}, jwt=False,
            gen_res=False, gen_db=False,
        )
        self.assertIsNone(bs.sql)
        self.assertIsNone(bs.sqlite)

    # --- setupDashboard ---
    def test_setupDashboard_missingBuild_warnsNoExcept(self):
        with mock.patch("bottler.core.DIST", "/nonexistent/dashboard/dist"):
            bs = Bottler(
                cfg_file=NONEXISTENT_CFG, dashboard=True, jwt="k", sqlite=False,
                sql=False, gen_res=False, gen_db=False,
            )
        self.assertTrue(any(r.rule.startswith("/dashboard") for r in bs.routes))

    def test_setupDashboard_buildFound_noWarning(self):
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        with open(os.path.join(tmp_dir, "index.html"), "w") as f:
            f.write("<html></html>")
        with mock.patch("bottler.core.DIST", tmp_dir):
            bs = Bottler(
                cfg_file=NONEXISTENT_CFG, dashboard=True, jwt="k", sqlite=False,
                sql=False, gen_res=False, gen_db=False,
            )
        self.assertTrue(any(r.rule.startswith("/dashboard") for r in bs.routes))

    def test_dashboardAndNuxt_routeHandlers_invoked(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, dashboard=True, jwt="k", sqlite=False,
            sql=False, gen_res=False, gen_db=False,
        )
        app = webtest.TestApp(bs)
        self.assertEqual(app.get("/dashboard").status_code, 200)
        # Real dashboard build has no such nuxt asset -> 404, but the
        # handler body itself still runs (that's what's being covered).
        app.get("/dashboard/_nuxt/does-not-exist.js", expect_errors=True)

    def test_dashboard_servesExistingStaticAsset(self):
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        with open(os.path.join(tmp_dir, "index.html"), "w") as f:
            f.write("<html>spa shell</html>")
        os.mkdir(os.path.join(tmp_dir, "vendor"))
        with open(os.path.join(tmp_dir, "vendor", "foo.js"), "w") as f:
            f.write("window.Redoc = {};")
        with mock.patch("bottler.core.DIST", tmp_dir):
            bs = Bottler(
                cfg_file=NONEXISTENT_CFG, dashboard=True, jwt="k", sqlite=False,
                sql=False, gen_res=False, gen_db=False,
            )
            app = webtest.TestApp(bs)
            resp = app.get("/dashboard/vendor/foo.js")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.body, b"window.Redoc = {};")

    def test_dashboard_unknownSubRoute_fallsBackToIndexHtml(self):
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        with open(os.path.join(tmp_dir, "index.html"), "w") as f:
            f.write("<html>spa shell</html>")
        with mock.patch("bottler.core.DIST", tmp_dir):
            bs = Bottler(
                cfg_file=NONEXISTENT_CFG, dashboard=True, jwt="k", sqlite=False,
                sql=False, gen_res=False, gen_db=False,
            )
            app = webtest.TestApp(bs)
            resp = app.get("/dashboard/resources/123")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.body, b"<html>spa shell</html>")

    def test_setupDashboard_wiresOwnTokenPath_leavesTokenAlone(self):
        from bottler.plugins.jwt import authFunc

        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, dashboard=True, jwt="k", sqlite=False,
            sql=False, gen_res=False, gen_db=False,
        )
        self.assertEqual(
            bs.jwt.token_paths["dashboardtoken"], bs.dashboard_token.authenticate
        )
        self.assertIs(bs.jwt.token_paths["token"], authFunc)
        self.assertTrue(any(r.rule == "/dashboard/token" for r in bs.routes))

    def test_setupDashboard_dictConfig_enabledKeyRespected(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, dashboard={"enabled": False}, jwt="k",
            sqlite=False, sql=False, gen_res=False, gen_db=False,
        )
        self.assertIsNone(bs.dashboard_token)
        self.assertFalse(any(r.rule.startswith("/dashboard") for r in bs.routes))

        bs2 = Bottler(
            cfg_file=NONEXISTENT_CFG, dashboard={"enabled": True}, jwt="k",
            sqlite=False, sql=False, gen_res=False, gen_db=False,
        )
        self.assertIsNotNone(bs2.dashboard_token)
        self.assertTrue(any(r.rule.startswith("/dashboard") for r in bs2.routes))

    # --- checkDashboardRequirements ---
    def test_dashboardMissingJwt_nonInteractive_raises(self):
        with mock.patch("sys.stdin.isatty", return_value=False):
            with self.assertRaises(Exception):
                Bottler(
                    cfg_file=NONEXISTENT_CFG, dashboard=True, jwt=False,
                    sqlite=False, sql=False, gen_res=False, gen_db=False,
                )

    def test_dashboardMissingRest_nonInteractive_raises(self):
        with mock.patch("sys.stdin.isatty", return_value=False):
            with self.assertRaises(Exception):
                Bottler(
                    cfg_file=NONEXISTENT_CFG, dashboard=True, jwt="k", rest=False,
                    sqlite=False, sql=False, gen_res=False, gen_db=False,
                )

    def test_dashboardMissingBoth_nonInteractive_raises(self):
        with mock.patch("sys.stdin.isatty", return_value=False):
            with self.assertRaises(Exception):
                Bottler(
                    cfg_file=NONEXISTENT_CFG, dashboard=True, jwt=False, rest=False,
                    sqlite=False, sql=False, gen_res=False, gen_db=False,
                )

    def test_dashboardMissingRest_interactive_accept_enablesRest(self):
        path = self._writeCfg("")
        with mock.patch("sys.stdin.isatty", return_value=True), mock.patch(
            "builtins.input", return_value="y"
        ):
            bs = Bottler(
                cfg_file=path, dashboard=True, jwt="k", rest=False,
                sqlite=False, sql=False, gen_res=False, gen_db=False,
            )
        self.assertIsNotNone(bs.rest)
        self.assertIs(bs.cfg["rest"], True)
        self.assertTrue(any(r.rule == "/dashboard/token" for r in bs.routes))

    def test_dashboardMissingJwt_interactive_accept_enablesJwt(self):
        path = self._writeCfg("")
        with mock.patch("sys.stdin.isatty", return_value=True), mock.patch(
            "builtins.input", return_value=""
        ):
            bs = Bottler(
                cfg_file=path, dashboard=True, jwt=False, sqlite=False,
                sql=False, gen_res=False, gen_db=False,
            )
        self.assertIsNotNone(bs.jwt)
        self.assertIsInstance(bs.cfg["jwt"], str)
        self.assertTrue(any(r.rule == "/dashboard/token" for r in bs.routes))

    def test_dashboardMissingBoth_interactive_accept_enablesBoth(self):
        path = self._writeCfg("")
        with mock.patch("sys.stdin.isatty", return_value=True), mock.patch(
            "builtins.input", return_value="yes"
        ):
            bs = Bottler(
                cfg_file=path, dashboard=True, jwt=False, rest=False,
                sqlite=False, sql=False, gen_res=False, gen_db=False,
            )
        self.assertIsNotNone(bs.rest)
        self.assertIsNotNone(bs.jwt)
        self.assertIs(bs.cfg["rest"], True)
        self.assertIsInstance(bs.cfg["jwt"], str)

    def test_dashboardMissingDeps_interactive_decline_disablesDashboard(self):
        with mock.patch("sys.stdin.isatty", return_value=True), mock.patch(
            "builtins.input", return_value="n"
        ):
            bs = Bottler(
                cfg_file=NONEXISTENT_CFG, dashboard=True, jwt=False, rest=False,
                sqlite=False, sql=False, gen_res=False, gen_db=False,
            )
        self.assertIsNone(bs.dashboard_token)
        self.assertFalse(any(r.rule.startswith("/dashboard") for r in bs.routes))

    # --- setupRest ---
    def test_setupRest_genTrue_noResourcesDir_noop(self):
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            bs = Bottler(
                cfg_file=NONEXISTENT_CFG, rest=True, gen_res=True, gen_db=False,
                jwt=False, sqlite=False, sql=False,
            )
            self.assertIsNotNone(bs.rest)
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp)

    def test_setupRest_genTrue_removesSysPathEntryItAdded(self):
        cwd = os.getcwd()
        was_present = cwd in sys.path
        if was_present:
            sys.path.remove(cwd)
        try:
            Bottler(gen_res=True, gen_db=False)
            self.assertNotIn(cwd, sys.path)
            self.assertNotIn("resources", sys.modules)
            self.assertFalse(any(n.startswith("resources.") for n in sys.modules))
        finally:
            if was_present:
                sys.path.insert(0, cwd)

    def test_importResourcesDir_globalApiPrefix_prependsResourceRoutes(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, api_prefix="/api", jwt=False,
            sqlite=False, sql=False, gen_res=True, gen_db=False,
        )
        app = webtest.TestApp(bs)
        self.assertEqual(app.get("/api/file_resource").status_code, 200)
        self.assertEqual(
            app.get("/file_resource", expect_errors=True).status_code, 404
        )

    def test_importResourcesDir_resourceApiPrefixOverride_bypassesGlobalPrefix(self):
        # tests/resources/api_prefix_override_resource.py sets api_prefix =
        # "" as a class attribute -- it must stay unprefixed even when the
        # app's own global api_prefix is set, the way a root-mounted SPA/
        # static-file resource needs to.
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, api_prefix="/api", jwt=False,
            sqlite=False, sql=False, gen_res=True, gen_db=False,
        )
        app = webtest.TestApp(bs)
        self.assertEqual(app.get("/api_prefix_override_resource").status_code, 200)
        self.assertEqual(
            app.get("/api/api_prefix_override_resource", expect_errors=True).status_code,
            404,
        )

    def test_deferredResource_catchAll_doesNotShadowDbAutoCrudRoute(self):
        # Regression: server/resources/spa.py-style catch-all (api_prefix="")
        # must never shadow a real, default-prefixed dynamic route (e.g. a DB
        # auto-CRUD /<table>/<key>), regardless of Bottle's first-match-wins
        # dynamic-route registration order and os.listdir()'s unspecified
        # ordering of tests/resources/*.py.
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        path = self._writeCfg(
            '[resources.catchall_override_resource]\npaths = ["/", "/<path:path>"]\n'
        )
        bs = Bottler(
            cfg_file=path, api_prefix="/api", sqlite=tmp_db, jwt=False,
            gen_res=True, gen_db=True,
        )
        app = webtest.TestApp(bs)
        resp = app.get("/api/animals/1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json["name"], "dog")
        # Sanity: the catch-all itself still works for genuinely unclaimed paths.
        self.assertEqual(
            app.get("/anything-else").json["caught_by"], "catchall_override_resource"
        )

    def test_setupRest_genTrue_leavesPreexistingSysPathEntry(self):
        cwd = os.getcwd()
        was_present = cwd in sys.path
        if not was_present:
            sys.path.insert(0, cwd)
        try:
            Bottler(gen_res=True, gen_db=False)
            self.assertIn(cwd, sys.path)
            self.assertNotIn("resources", sys.modules)
        finally:
            if not was_present:
                sys.path.remove(cwd)

    # --- setRoles: preexisting bool roles + toml roles -> TypeError is
    # swallowed by setRoles' own broad except, not raised (characterized).
    def test_setRoles_preexistingBoolRoles_printsAndSkips(self):
        class BoolRolesResource(bottle_rest.Resource):
            GET = {"roles": True}

            def options(self):
                pass

            def get(self):
                return {}

        path = self._writeCfg('[resources.boolroles.roles]\nget = ["admin"]\n')
        bs = Bottler(
            cfg_file=path, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.setRoles(BoolRolesResource, "boolroles")  # should not raise
        cfg = BoolRolesResource.getRouteConfig(bottle_rest.Resource.Methods.GET)
        self.assertEqual(cfg["roles"], True)

    # --- createResForDB ---
    def test_createResForDB_misconfigured_raises(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, rest=False, sqlite=False, sql=False,
            jwt=False, gen_res=False, gen_db=False,
        )
        with self.assertRaises(Exception):
            bs.createResForDB()

    def test_createResForDB_skipsTableWithoutPrimaryKey_mysqlMocked(self):
        # Regression for fix #3.
        cursor = make_mysql_cursor()
        patcher, mock_conn, cursor = patch_pymysql_connect(cursor)
        patcher.start()
        self.addCleanup(patcher.stop)
        cursor.fetchall.side_effect = [
            [{"name": "nokey"}],
            [{"Field": "name", "Type": "TEXT", "Null": "YES", "Default": None, "Key": ""}],
        ]
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG,
            sql={"host": "h", "user": "u", "password": "p", "database": "d"},
            sqlite=False, jwt=False, gen_res=False, gen_db=False,
        )
        bs.createResForDB()
        self.assertNotIn("Nokey", bs.resource_names)

    def test_createResForDB_apiPrefix_prependsGeneratedRoutes(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, api_prefix="/api", sqlite=tmp_db,
            jwt=False, gen_res=False, gen_db=True,
        )
        app = webtest.TestApp(bs)
        self.assertEqual(app.get("/api/animals").status_code, 200)
        self.assertEqual(app.get("/api/animals/1").status_code, 200)
        self.assertEqual(app.get("/animals", expect_errors=True).status_code, 404)

    def test_createResForDB_multipleExtraPaths_allAdded(self):
        # Exercises the extra-paths for-loop iterating more than once, both
        # while appending new paths (first call) and while skipping paths
        # already routed (second call, covering the "path not in rules" ==
        # False -> continue-loop arc).
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        path = self._writeCfg(
            f'sqlite = "{tmp_db}"\n[resources.animals]\npaths = ["/nmls", "/critters"]\n'
        )
        bs = Bottler(cfg_file=path, jwt=False, gen_res=False, gen_db=True)
        app = webtest.TestApp(bs)
        self.assertEqual(app.get("/nmls").status_code, 200)
        self.assertEqual(app.get("/critters").status_code, 200)
        bs.createResForDB()  # both paths already routed this time

    def test_createResForDB_calledAgain_allEndpointsAlreadyRouted_noop(self):
        # Second call: every endpoint createResForDB would add is already in
        # self.routes, so all three `not in rules` checks are False and the
        # per-table `endpoints` list stays empty -- addResource is skipped.
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=True,
        )
        names_before = set(bs.resource_names)
        bs.createResForDB()
        self.assertEqual(set(bs.resource_names), names_before)

    # --- getDBCursor ---
    def test_getDBCursor_sqlite(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        db = bs.getDBCursor()
        db.execute("select * from animals where id=1")
        row = db.fetchone()
        self.assertEqual(row["name"], "dog")

    def test_getDBCursor_mysqlMocked(self):
        cursor = make_mysql_cursor(fetchone={"id": 1})
        patcher, mock_conn, cursor = patch_pymysql_connect(cursor)
        patcher.start()
        self.addCleanup(patcher.stop)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG,
            sql={"host": "h", "user": "u", "password": "p", "database": "d"},
            sqlite=False, jwt=False, gen_res=False, gen_db=False,
        )
        db = bs.getDBCursor()
        self.assertIs(db, cursor)

    def test_getDBCursor_neitherConfigured_raisesClearException(self):
        # Regression for fix #11.
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=False, sql=False, jwt=False,
            gen_res=False, gen_db=False,
        )
        with self.assertRaises(Exception):
            bs.getDBCursor()

    def test_getDBTables_neitherConfigured_raisesClearException(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=False, sql=False, jwt=False,
            gen_res=False, gen_db=False,
        )
        with self.assertRaises(Exception):
            bs.getDBTables()

    def test_getDBTables_mysqlMocked_pragmaFailsFallsBackToDescribe(self):
        cursor = make_mysql_cursor()
        patcher, mock_conn, cursor = patch_pymysql_connect(cursor)
        patcher.start()
        self.addCleanup(patcher.stop)
        cursor.execute.side_effect = pragma_raises_side_effect()
        cursor.fetchall.side_effect = [
            [{"name": "widgets"}],
            [{"Field": "id", "Type": "INTEGER", "Null": "NO", "Default": None, "Key": "PRI"}],
        ]
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG,
            sql={"host": "h", "user": "u", "password": "p", "database": "d"},
            sqlite=False, jwt=False, gen_res=False, gen_db=False,
        )
        tables = bs.getDBTables()
        self.assertIn("widgets", tables)
        self.assertEqual(tables["widgets"][0]["key"], 1)

    def test_getDBTables_cursorMatchesNeitherType_characterized(self):
        # getDBCursor()'s own connection-setup guarantees db is always a
        # sqlite3.Cursor or pymysql.cursors.Cursor in real use; this
        # documents what happens if that invariant is ever violated (e.g. by
        # a misbehaving mock/driver) -- tables_sql is never assigned, and
        # `db.execute` itself fails first since db isn't a real cursor.
        mock_conn = mock.MagicMock()
        mock_conn.cursor.return_value = object()
        with mock.patch("pymysql.connect", return_value=mock_conn):
            bs = Bottler(
                cfg_file=NONEXISTENT_CFG,
                sql={"host": "h", "user": "u", "password": "p", "database": "d"},
                sqlite=False, jwt=False, gen_res=False, gen_db=False,
            )
            with self.assertRaises(AttributeError):
                bs.getDBTables()

    # --- createTable / alterDBTable ---
    def test_createTable_sqlite(self):
        # Regression for fix #13 (self.sqlite.dbfile -> sql_config["database"]).
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        bs.createTable("widgets")
        self.assertIn("widgets", bs.getDBTables())

    def test_createTable_invalidName_raisesValueError(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        with self.assertRaises(ValueError):
            bs.createTable("bad name")

    def test_createTable_duplicateName_raisesOperationalError(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        bs.createTable("widgets")
        with self.assertRaises(sqlite3.OperationalError):
            bs.createTable("widgets")

    def test_alterDBTable_sqlite_renameColumn(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        bs.alterDBTable(
            "animals",
            {"cid": 1, "name": "animal_name", "type": "TEXT", "notnull": 0,
             "dflt_value": None, "pk": 0},
        )
        fields = bs.getDBTable(bs.getDBCursor(), "animals")
        self.assertIn("animal_name", [f["name"] for f in fields])

    def test_alterDBTable_sqlite_addColumn(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        bs.alterDBTable(
            "animals",
            {"cid": None, "name": "age", "type": "INTEGER", "notnull": 0,
             "dflt_value": None, "pk": 0},
        )
        fields = bs.getDBTable(bs.getDBCursor(), "animals")
        self.assertIn("age", [f["name"] for f in fields])

    def test_alterDBTable_sqlite_notnullNoDefault_getsPlaceholder(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        bs.alterDBTable(
            "animals",
            {"cid": None, "name": "required_field", "type": "TEXT", "notnull": 1,
             "dflt_value": None, "pk": 0},
        )
        fields = bs.getDBTable(bs.getDBCursor(), "animals")
        self.assertIn("required_field", [f["name"] for f in fields])

    def test_alterDBTable_sqlite_neitherRenameNorAdd_noop(self):
        # cid doesn't match any existing column AND name is falsy -> neither
        # branch executes; still commits and reloads without error.
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        bs.alterDBTable(
            "animals",
            {"cid": 999, "name": "", "type": "TEXT", "notnull": 0,
             "dflt_value": None, "pk": 0},
        )
        fields = bs.getDBTable(bs.getDBCursor(), "animals")
        self.assertEqual(sorted(f["name"] for f in fields), ["id", "name"])

    def test_createTable_mysqlConfigured_isNoop_characterized(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=False,
            sql={"host": "h", "user": "u", "password": "p", "database": "d"},
            jwt=False, gen_res=False, gen_db=False,
        )
        bs.createTable("widgets")  # no crash, no real connection attempted

    def test_alterDBTable_mysqlMocked_addColumn_success(self):
        cursor = make_mysql_cursor(
            fetchall=[("id", "INTEGER", "NO", "PRI", None, "auto_increment"),
                      ("name", "TEXT", "YES", "", None, "")]
        )
        patcher, mock_conn, cursor = patch_pymysql_connect(cursor)
        patcher.start()
        self.addCleanup(patcher.stop)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=False,
            sql={"host": "h", "user": "u", "password": "p", "database": "d"},
            jwt=False, gen_res=False, gen_db=False,
        )
        bs.alterDBTable(
            "widgets",
            {"cid": None, "name": "age", "type": "INT", "notnull": 0,
             "dflt_value": None, "pk": 0},
        )
        sql = cursor.execute.call_args_list[-1][0][0]
        self.assertIn("ADD COLUMN age INT", sql)
        mock_conn.commit.assert_called()

    def test_alterDBTable_mysqlMocked_renameColumn_success(self):
        cursor = make_mysql_cursor(
            fetchall=[("id", "INTEGER", "NO", "PRI", None, "auto_increment"),
                      ("name", "TEXT", "YES", "", None, "")]
        )
        patcher, mock_conn, cursor = patch_pymysql_connect(cursor)
        patcher.start()
        self.addCleanup(patcher.stop)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=False,
            sql={"host": "h", "user": "u", "password": "p", "database": "d"},
            jwt=False, gen_res=False, gen_db=False,
        )
        bs.alterDBTable(
            "widgets",
            {"cid": "name", "name": "widget_name", "type": "TEXT", "notnull": 0,
             "dflt_value": None, "pk": 0},
        )
        sql = cursor.execute.call_args_list[-1][0][0]
        self.assertIn("RENAME COLUMN name TO widget_name", sql)
        mock_conn.commit.assert_called()

    def test_alterDBTable_mysqlMocked_neitherRenameNorAdd_noop(self):
        cursor = make_mysql_cursor(
            fetchall=[("id", "INTEGER", "NO", "PRI", None, "auto_increment")]
        )
        patcher, mock_conn, cursor = patch_pymysql_connect(cursor)
        patcher.start()
        self.addCleanup(patcher.stop)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=False,
            sql={"host": "h", "user": "u", "password": "p", "database": "d"},
            jwt=False, gen_res=False, gen_db=False,
        )
        bs.alterDBTable(
            "widgets",
            {"cid": None, "name": "", "type": "TEXT", "notnull": 0,
             "dflt_value": None, "pk": 0},
        )
        mock_conn.commit.assert_called()

    def test_alterDBTable_mysqlMocked_addColumn_notnullNoDefault_getsPlaceholder(self):
        cursor = make_mysql_cursor(
            fetchall=[("id", "INTEGER", "NO", "PRI", None, "auto_increment")]
        )
        patcher, mock_conn, cursor = patch_pymysql_connect(cursor)
        patcher.start()
        self.addCleanup(patcher.stop)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=False,
            sql={"host": "h", "user": "u", "password": "p", "database": "d"},
            jwt=False, gen_res=False, gen_db=False,
        )
        bs.alterDBTable(
            "widgets",
            {"cid": None, "name": "required_field", "type": "TEXT", "notnull": 1,
             "dflt_value": None, "pk": 0},
        )
        sql = cursor.execute.call_args_list[-1][0][0]
        self.assertIn("DEFAULT ''", sql)

    def test_alterDBTable_noDbConfigured_noop(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=False, sql=False, jwt=False,
            gen_res=False, gen_db=False,
        )
        bs.alterDBTable(
            "widgets",
            {"cid": None, "name": "age", "type": "INTEGER", "notnull": 0,
             "dflt_value": None, "pk": 0},
        )

    def test_alterDBTable_mysqlMocked_addColumn_invalidDatatype_raisesValueError(self):
        cursor = make_mysql_cursor(
            fetchall=[("id", "INTEGER", "NO", "PRI", None, "auto_increment")]
        )
        patcher, mock_conn, cursor = patch_pymysql_connect(cursor)
        patcher.start()
        self.addCleanup(patcher.stop)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=False,
            sql={"host": "h", "user": "u", "password": "p", "database": "d"},
            jwt=False, gen_res=False, gen_db=False,
        )
        with self.assertRaises(ValueError):
            bs.alterDBTable(
                "widgets",
                {"cid": None, "name": "age", "type": "INT); DROP TABLE widgets;--",
                 "notnull": 0, "dflt_value": None, "pk": 0},
            )

    def test_alterDBTable_invalidTableName_raisesValueError(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        with self.assertRaises(ValueError):
            bs.alterDBTable(
                "animals; DROP TABLE animals;--",
                {"cid": None, "name": "age", "type": "INTEGER", "notnull": 0,
                 "dflt_value": None, "pk": 0},
            )

    def test_alterDBTable_sqlite_addColumn_invalidColumnName_raisesValueError(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        with self.assertRaises(ValueError):
            bs.alterDBTable(
                "animals",
                {"cid": None, "name": "age); DROP TABLE animals;--",
                 "type": "INTEGER", "notnull": 0, "dflt_value": None, "pk": 0},
            )

    def test_alterDBTable_sqlite_renameColumn_invalidNewName_raisesValueError(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        with self.assertRaises(ValueError):
            bs.alterDBTable(
                "animals",
                {"cid": 1, "name": "bad name", "type": "TEXT", "notnull": 0,
                 "dflt_value": None, "pk": 0},
            )

    def test_alterDBTable_sqlite_addColumn_invalidDatatype_raisesValueError(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        with self.assertRaises(ValueError):
            bs.alterDBTable(
                "animals",
                {"cid": None, "name": "age", "type": "TEXT); DROP TABLE animals;--",
                 "notnull": 0, "dflt_value": None, "pk": 0},
            )

    def test_alterDBTable_sqlite_addColumn_emptyDatatype_defaultsToText(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        bs.alterDBTable(
            "animals",
            {"cid": None, "name": "notes", "type": "", "notnull": 0,
             "dflt_value": None, "pk": 0},
        )
        fields = bs.getDBTable(bs.getDBCursor(), "animals")
        field = next(f for f in fields if f["name"] == "notes")
        self.assertEqual(field["type"], "TEXT")

    def test_alterDBTable_sqlite_addColumn_invalidDefaultValue_raisesValueError(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        with self.assertRaises(ValueError):
            bs.alterDBTable(
                "animals",
                {"cid": None, "name": "age", "type": "INTEGER", "notnull": 0,
                 "dflt_value": "1); DROP TABLE animals;--", "pk": 0},
            )

    def test_alterDBTable_sqlite_addColumn_validDefaultValue(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        bs.alterDBTable(
            "animals",
            {"cid": None, "name": "age", "type": "INTEGER", "notnull": 0,
             "dflt_value": "5", "pk": 0},
        )
        fields = bs.getDBTable(bs.getDBCursor(), "animals")
        self.assertIn("age", [f["name"] for f in fields])

    # --- alterDBTable: drop column ---
    def test_alterDBTable_sqlite_dropColumn_removesColumn(self):
        # "animals" has no FK-referenced columns, unlike "predations"
        # (predator/prey are referenced by a FOREIGN KEY definition and
        # sqlite itself refuses to drop them) -- picking a column with no
        # such constraint isolates the drop-column logic under test from
        # that (correct, relied-upon) native DB enforcement.
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        cfg_dir, cfg_path = db_fixtures.temp_cfg_pointing_at(tmp_db)
        self.addCleanup(shutil.rmtree, cfg_dir)
        bs = Bottler(cfg_file=cfg_path, jwt=False, gen_res=False, gen_db=False)
        fields = bs.getDBTable(bs.getDBCursor(), "animals")
        name_field = next(f for f in fields if f["name"] == "name")
        bs.alterDBTable(
            "animals", {"cid": fields.index(name_field), "drop": True}
        )
        fields = bs.getDBTable(bs.getDBCursor(), "animals")
        self.assertNotIn("name", [f["name"] for f in fields])

    def test_alterDBTable_sqlite_dropColumn_unknownCid_raisesValueError(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        with self.assertRaises(ValueError):
            bs.alterDBTable("animals", {"cid": 999, "drop": True})

    def test_alterDBTable_sqlite_dropColumn_primaryKey_raisesValueError(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        fields = bs.getDBTable(bs.getDBCursor(), "animals")
        pk_index = next(i for i, f in enumerate(fields) if f["key"] == 1)
        with self.assertRaises(ValueError):
            bs.alterDBTable("animals", {"cid": pk_index, "drop": True})

    def test_alterDBTable_sqlite_dropColumn_lastColumn_raisesValueError(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        db = bs.getDBCursor()
        db.execute("CREATE TABLE onecol (val TEXT)")
        with self.assertRaises(ValueError):
            bs.alterDBTable("onecol", {"cid": 0, "drop": True})

    def test_alterDBTable_sqlite_dropColumn_oldSqliteVersion_raisesRuntimeError(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        fields = bs.getDBTable(bs.getDBCursor(), "animals")
        non_pk_index = next(i for i, f in enumerate(fields) if f["key"] != 1)
        with mock.patch("sqlite3.sqlite_version_info", (3, 30, 0)):
            with self.assertRaises(RuntimeError):
                bs.alterDBTable("animals", {"cid": non_pk_index, "drop": True})

    def test_alterDBTable_mysqlMocked_dropColumn_success(self):
        cursor = make_mysql_cursor(
            fetchall=[("id", "INTEGER", "NO", "PRI", None, "auto_increment"),
                      ("name", "TEXT", "YES", "", None, "")]
        )
        patcher, mock_conn, cursor = patch_pymysql_connect(cursor)
        patcher.start()
        self.addCleanup(patcher.stop)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=False,
            sql={"host": "h", "user": "u", "password": "p", "database": "d"},
            jwt=False, gen_res=False, gen_db=False,
        )
        bs.alterDBTable("widgets", {"name": "name", "drop": True})
        mock_conn.commit.assert_called()

    def test_alterDBTable_mysqlMocked_dropColumn_primaryKey_raisesValueError(self):
        cursor = make_mysql_cursor(
            fetchall=[("id", "INTEGER", "NO", "PRI", None, "auto_increment"),
                      ("name", "TEXT", "YES", "", None, "")]
        )
        patcher, mock_conn, cursor = patch_pymysql_connect(cursor)
        patcher.start()
        self.addCleanup(patcher.stop)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=False,
            sql={"host": "h", "user": "u", "password": "p", "database": "d"},
            jwt=False, gen_res=False, gen_db=False,
        )
        with self.assertRaises(ValueError):
            bs.alterDBTable("widgets", {"name": "id", "drop": True})

    def test_alterDBTable_mysqlMocked_dropColumn_unknownColumn_raisesValueError(self):
        cursor = make_mysql_cursor(
            fetchall=[("id", "INTEGER", "NO", "PRI", None, "auto_increment")]
        )
        patcher, mock_conn, cursor = patch_pymysql_connect(cursor)
        patcher.start()
        self.addCleanup(patcher.stop)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=False,
            sql={"host": "h", "user": "u", "password": "p", "database": "d"},
            jwt=False, gen_res=False, gen_db=False,
        )
        with self.assertRaises(ValueError):
            bs.alterDBTable("widgets", {"name": "nonexistent", "drop": True})

    def test_alterDBTable_mysqlMocked_dropColumn_lastColumn_raisesValueError(self):
        cursor = make_mysql_cursor(
            fetchall=[("val", "TEXT", "YES", "", None, "")]
        )
        patcher, mock_conn, cursor = patch_pymysql_connect(cursor)
        patcher.start()
        self.addCleanup(patcher.stop)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=False,
            sql={"host": "h", "user": "u", "password": "p", "database": "d"},
            jwt=False, gen_res=False, gen_db=False,
        )
        with self.assertRaises(ValueError):
            bs.alterDBTable("widgets", {"name": "val", "drop": True})

    # --- dropTable ---
    def test_dropTable_sqlite_removesTableAndCfg(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        cfg_dir, cfg_path = db_fixtures.temp_cfg_pointing_at(tmp_db)
        self.addCleanup(shutil.rmtree, cfg_dir)
        bs = Bottler(cfg_file=cfg_path, jwt=False, gen_res=False, gen_db=False)
        bs.getResourceConfig("predations")["paths"] = ["/predations"]
        bs.dropTable("predations")
        self.assertNotIn("predations", bs.getDBTables())
        self.assertNotIn("predations", bs.cfg.get("resources", {}))

    def test_dropTable_unknownTable_raisesValueError(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        with self.assertRaises(ValueError):
            bs.dropTable("nonexistent")

    def test_dropTable_mysqlMocked_success(self):
        # dropTable() calls saveConfig() on success -- use a real (cleaned
        # up) temp cfg file rather than NONEXISTENT_CFG, which would
        # otherwise get created as a stray file in tests/ (open(..., "w+")
        # creates it if missing).
        path = self._writeCfg("")
        cursor = make_mysql_cursor()
        patcher, mock_conn, cursor = patch_pymysql_connect(cursor)
        patcher.start()
        self.addCleanup(patcher.stop)
        cursor.fetchall.side_effect = [
            [{"name": "widgets"}],
            [{"Field": "id", "Type": "INTEGER", "Null": "NO", "Default": None, "Key": "PRI"}],
        ]
        bs = Bottler(
            cfg_file=path, sqlite=False,
            sql={"host": "h", "user": "u", "password": "p", "database": "d"},
            jwt=False, gen_res=False, gen_db=False,
        )
        bs.dropTable("widgets")
        mock_conn.commit.assert_called()
        mock_conn.close.assert_called()

    # --- deleteResourceFile ---
    def test_deleteResourceFile_removesFileAndCfg(self):
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            bs = Bottler(
                cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
                gen_res=False, gen_db=False,
            )
            bs.createResourceFile("widget")
            bs.deleteResourceFile("widget")
            self.assertFalse(
                os.path.exists(os.path.join(tmp, "resources", "widget.py"))
            )
            self.assertNotIn("widget", bs.cfg.get("resources", {}))
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp)

    def test_deleteResourceFile_missingFile_raisesFileNotFoundError(self):
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            bs = Bottler(
                cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
                gen_res=False, gen_db=False,
            )
            with self.assertRaises(FileNotFoundError):
                bs.deleteResourceFile("nonexistent")
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp)

    # --- removePath ---
    def test_removePath_validIndex_removes(self):
        path = self._writeCfg("")
        bs = Bottler(
            cfg_file=path, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.updatePaths("widgets", 0, "/a")
        bs.updatePaths("widgets", 1, "/b")
        bs.removePath("widgets", 0)
        self.assertEqual(bs.cfg["resources"]["widgets"]["paths"], ["/b"])

    def test_removePath_outOfRangeIndex_noop(self):
        path = self._writeCfg("")
        bs = Bottler(
            cfg_file=path, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.updatePaths("widgets", 0, "/a")
        bs.removePath("widgets", 5)
        self.assertEqual(bs.cfg["resources"]["widgets"]["paths"], ["/a"])

    def test_removePath_noPathsYet_noop(self):
        path = self._writeCfg("")
        bs = Bottler(
            cfg_file=path, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.removePath("widgets", 0)
        self.assertEqual(bs.cfg["resources"]["widgets"]["paths"], [])

    # --- getResourceConfig / updatePaths / updateRoles / saveConfig ---
    def test_getResourceConfig_freshConfigNoResourcesKey(self):
        # Regression for fix #5.
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        self.assertNotIn("resources", bs.cfg)
        cfg = bs.getResourceConfig("widgets")
        self.assertEqual(cfg, {})
        self.assertIn("resources", bs.cfg)

    def test_updatePaths_indexOutOfRange_appends(self):
        path = self._writeCfg("")
        bs = Bottler(
            cfg_file=path, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.updatePaths("widgets", 5, "/widgets")
        self.assertEqual(bs.cfg["resources"]["widgets"]["paths"], ["/widgets"])

    def test_updatePaths_validIndex_overwrites(self):
        path = self._writeCfg("")
        bs = Bottler(
            cfg_file=path, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.updatePaths("widgets", 0, "/a")
        bs.updatePaths("widgets", 0, "/b")
        self.assertEqual(bs.cfg["resources"]["widgets"]["paths"], ["/b"])

    def test_updateRoles_stringTrueFalse(self):
        path = self._writeCfg("")
        bs = Bottler(
            cfg_file=path, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.updateRoles("widgets", "get", "true")
        self.assertEqual(bs.cfg["resources"]["widgets"]["roles"]["get"], True)
        bs.updateRoles("widgets", "get", "false")
        self.assertEqual(bs.cfg["resources"]["widgets"]["roles"]["get"], False)

    def test_updateRoles_commaSeparatedString(self):
        path = self._writeCfg("")
        bs = Bottler(
            cfg_file=path, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.updateRoles("widgets", "get", "admin,user")
        self.assertEqual(
            bs.cfg["resources"]["widgets"]["roles"]["get"], ["admin", "user"]
        )

    def test_updateRoles_listInput_noCrash(self):
        # Regression for fix #6.
        path = self._writeCfg("")
        bs = Bottler(
            cfg_file=path, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.updateRoles("widgets", "get", ["admin"])
        self.assertEqual(bs.cfg["resources"]["widgets"]["roles"]["get"], ["admin"])

    def test_updateRoles_boolInput_noCrash(self):
        path = self._writeCfg("")
        bs = Bottler(
            cfg_file=path, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.updateRoles("widgets", "get", True)
        self.assertEqual(bs.cfg["resources"]["widgets"]["roles"]["get"], True)

    def test_updateRoles_bulkMethodList_appliesToAll(self):
        path = self._writeCfg("")
        bs = Bottler(
            cfg_file=path, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.updateRoles("widgets", ["put", "patch", "delete"], ["admin"])
        roles = bs.cfg["resources"]["widgets"]["roles"]
        self.assertEqual(roles["put"], ["admin"])
        self.assertEqual(roles["patch"], ["admin"])
        self.assertEqual(roles["delete"], ["admin"])

    def test_updateRolesBulk_multipleResources_bothUpdated(self):
        path = self._writeCfg("")
        bs = Bottler(
            cfg_file=path, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.updateRolesBulk(
            [
                {"resource": "widgets", "method": "get", "roles": ["admin"]},
                {"resource": "gadgets", "method": "post", "roles": True},
            ]
        )
        self.assertEqual(bs.cfg["resources"]["widgets"]["roles"]["get"], ["admin"])
        self.assertEqual(bs.cfg["resources"]["gadgets"]["roles"]["post"], True)

    def test_updateRolesBulk_methodList_appliesToAll(self):
        path = self._writeCfg("")
        bs = Bottler(
            cfg_file=path, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.updateRolesBulk(
            [{"resource": "widgets", "method": ["put", "patch"], "roles": ["admin"]}]
        )
        roles = bs.cfg["resources"]["widgets"]["roles"]
        self.assertEqual(roles["put"], ["admin"])
        self.assertEqual(roles["patch"], ["admin"])

    def test_updateRolesBulk_savesAndReloadsExactlyOnce(self):
        path = self._writeCfg("")
        bs = Bottler(
            cfg_file=path, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        with mock.patch.object(bs, "saveConfig") as save, mock.patch.object(
            bs, "reloadServer"
        ) as reload_:
            bs.updateRolesBulk(
                [
                    {"resource": "widgets", "method": "get", "roles": True},
                    {"resource": "gadgets", "method": "post", "roles": True},
                    {"resource": "gizmos", "method": "delete", "roles": ["admin"]},
                ]
            )
            save.assert_called_once()
            reload_.assert_called_once()

    def test_updateRolesBulk_emptyList_stillSavesOnceNoCrash(self):
        path = self._writeCfg("")
        bs = Bottler(
            cfg_file=path, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        with mock.patch.object(bs, "saveConfig") as save, mock.patch.object(
            bs, "reloadServer"
        ) as reload_:
            bs.updateRolesBulk([])
            save.assert_called_once()
            reload_.assert_called_once()

    def test_updateRolesBulk_missingKey_raisesKeyError(self):
        path = self._writeCfg("")
        bs = Bottler(
            cfg_file=path, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        with self.assertRaises(KeyError):
            bs.updateRolesBulk([{"resource": "widgets", "roles": True}])

    def test_saveConfig_errorSwallowed_noRaise(self):
        # A directory path for cfg_file makes open(cfg_file, "w+") raise
        # IsADirectoryError; toml.load() on it at construction time is
        # likewise caught by the bare except, so self.cfg starts as {}.
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        bs = Bottler(
            cfg_file=tmp_dir, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.saveConfig()  # should not raise

    # --- createResourceFile ---
    def test_createResourceFile_writesStubAndCfg(self):
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            bs = Bottler(
                cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
                gen_res=False, gen_db=False,
            )
            result = bs.createResourceFile("Widget")
            self.assertEqual(result, "widget")
            with open(os.path.join(tmp, "resources", "widget.py")) as f:
                content = f.read()
            self.assertIn("class Widget(Resource):", content)
            self.assertEqual(
                bs.cfg["resources"]["widget"]["paths"], ["/widget", "/widget/<key>"]
            )
            on_disk = toml.load(NONEXISTENT_CFG)
            self.assertEqual(
                on_disk["resources"]["widget"]["paths"], ["/widget", "/widget/<key>"]
            )
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp)

    def test_createResourceFile_invalidName_raisesValueError(self):
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            bs = Bottler(
                cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
                gen_res=False, gen_db=False,
            )
            with self.assertRaises(ValueError):
                bs.createResourceFile("123bad")
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp)

    def test_createResourceFile_duplicateName_raisesFileExistsError(self):
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            bs = Bottler(
                cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
                gen_res=False, gen_db=False,
            )
            bs.createResourceFile("widget")
            with self.assertRaises(FileExistsError):
                bs.createResourceFile("widget")
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp)

    def test_reloadServer_writesFile(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.reloadServer()
        from bottler import reload as reload_module

        with open(reload_module.__file__) as f:
            content = f.read()
        self.assertIn("Used to force reload", content)

    # --- JSONEncoder ---
    def test_JSONEncoder_datetime(self):
        enc = JSONEncoder()
        dt = datetime.datetime(2020, 1, 2, 3, 4, 5)
        self.assertEqual(enc.default(dt), dt.isoformat())

    def test_JSONEncoder_date(self):
        enc = JSONEncoder()
        d = datetime.date(2020, 1, 2)
        self.assertEqual(enc.default(d), d.isoformat())

    def test_JSONEncoder_decimal(self):
        enc = JSONEncoder()
        self.assertEqual(enc.default(decimal.Decimal("1.5")), "1.5000")

    def test_JSONEncoder_fallsThroughToDefault_forUnknownType(self):
        enc = JSONEncoder()
        with self.assertRaises(TypeError):
            enc.default(object())

    # --- resource_names ---
    def test_resourceNames_noRest_returnsEmptySet(self):
        bs = Bottler(
            cfg_file=NONEXISTENT_CFG, rest=False, jwt=False, sqlite=False,
            sql=False, gen_res=False, gen_db=False,
        )
        self.assertEqual(bs.resource_names, set())

    def test_getSQLiteTable(self):
        with sqlite3.connect("resources.db") as conn:
            conn.row_factory = lambda cursor, row: {
                col[0]: row[idx] for idx, col in enumerate(cursor.description)
            }
            db = conn.cursor()
            table = self.bottler.getDBTable(db, "animals")
            self.assertDictEqual(
                table[0],
                {
                    "name": "id",
                    "type": "INTEGER",
                    "notnull": True,
                    "default": None,
                    "key": 1,
                },
            )
        conn.close()

    def test_getSQLiteTables(self):
        tables = self.bottler.getDBTables()
        self.assertIn("animals", tables)
        self.assertIn("predations", tables)

    def test_genResoursesForDB(self):
        self.bottler = Bottler()
        self.app = webtest.TestApp(self.bottler)
        self.assertIn("Animals", self.bottler.resource_names)
        self.assertIn("Predations", self.bottler.resource_names)
        self.assertEqual("dog", self.app.get("/animals/1").json["name"])
        self.assertEqual(6, self.app.get("/predations/1").json["predator"])

    # CORS
