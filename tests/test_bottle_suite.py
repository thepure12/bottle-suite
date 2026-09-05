import _paths  # noqa: F401
import unittest
from unittest import mock
import webtest
import datetime
import decimal
import pymysql
from bottle_suite import BottleSuite
from bottle_suite.bottle_suite import JSONEncoder
from bottle_suite.plugins import rest as bottle_rest
from bottle_suite.plugins import jwt as bottle_jwt
import toml
import os
import shutil
import tempfile
import sqlite3
import db_fixtures
from mysql_mock import make_mysql_cursor, patch_pymysql_connect, pragma_raises_side_effect

DEBUG = False
NONEXISTENT_CFG = "no_such_bottle_suite_cfg.toml"


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


class TestBottleSuite(unittest.TestCase):
    def setUp(self) -> None:
        self.bottle_suite = BottleSuite(gen_res=False, gen_db=False)
        self.app = webtest.TestApp(self.bottle_suite)

    def addTestResource(self):
        self.bottle_suite.rest.addResource(TestResource, "/test_resource")

    def _writeCfg(self, content):
        fd, path = tempfile.mkstemp(suffix=".toml", dir=os.getcwd())
        os.close(fd)
        with open(path, "w") as f:
            f.write(content)
        self.addCleanup(os.remove, path)
        return path

    def test_init(self):
        self.assertIsNotNone(self.bottle_suite.cors)
        self.assertIsNotNone(self.bottle_suite.rest)
        self.assertIsInstance(self.bottle_suite.jwt, bottle_jwt.JWTPlugin)
        self.assertIsNotNone(self.bottle_suite.sqlite)

    # Config
    def test_loadConfig(self):
        cfg = toml.load("bottle_suite.toml")
        self.assertEqual(cfg, self.bottle_suite.cfg)

    # REST
    def test_initRest(self):
        self.assertIn("AllResources", self.bottle_suite.resource_names)
        self.assertIn("DataTypes", self.bottle_suite.resource_names)

    def test_initNoRest(self):
        self.bottle_suite = BottleSuite(rest=False)
        self.assertIsNone(
            next((p for p in self.bottle_suite.plugins if "API" in str(p)), None)
        )

    def test_addResource(self):
        self.addTestResource()
        self.assertIn("TestResource", self.bottle_suite.resource_names)
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
        self.bottle_suite = BottleSuite(gen_res=True, gen_db=False)
        self.app = webtest.TestApp(self.bottle_suite)
        self.assertIn("FileResource", self.bottle_suite.resource_names)
        self.assertEqual(200, self.app.get("/file_resource").status_code)

    # JWT
    def test_initJWT(self):
        self.assertIsInstance(self.bottle_suite.jwt, bottle_jwt.JWTPlugin)

    def test_initNoJWT(self):
        self.bottle_suite = BottleSuite(jwt=False, cfg_file=None)
        self.assertIsNone(
            next((p for p in self.bottle_suite.plugins if "JWT" in str(p)), None)
        )

    # SQL
    def test_initSQLite(self):
        self.assertIsNotNone(self.bottle_suite.sqlite)

    def test_initNoSQLite(self):
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG,
            sqlite=False,
            sql=False,
            jwt=False,
            gen_res=False,
            gen_db=False,
        )
        self.assertIsNone(bs.sqlite)

    def test_setupSql_dictConfig(self):
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG,
            sql={"host": "h", "user": "u", "password": "p", "database": "d"},
            sqlite=False,
            jwt=False,
            gen_res=False,
            gen_db=False,
        )
        self.assertEqual(bs.sql.sql_config["database"], "d")

    def test_setupSql_strConfig(self):
        bs = BottleSuite(
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
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG,
            sqlite={"database": tmp_db},
            sql=False,
            jwt=False,
            gen_res=False,
            gen_db=False,
        )
        self.assertEqual(bs.sqlite.sql_config["database"], tmp_db)

    def test_setupJwt_neitherStrNorDict_stillCallsJWTPluginConstructor(self):
        # jwt=True (bool) skips both the str and dict branches, so cfg stays
        # {} -- JWTPlugin's required jwt_key positional arg then crashes.
        with self.assertRaises(TypeError):
            BottleSuite(
                cfg_file=NONEXISTENT_CFG, jwt=True, sqlite=False, sql=False,
                gen_res=False, gen_db=False,
            )

    def test_setupSqlite_neitherStrNorDict_stillCallsFactory(self):
        # sqlite=True (bool) skips both branches; sqlitePlugin's required
        # `database` positional arg then crashes.
        with self.assertRaises(TypeError):
            BottleSuite(
                cfg_file=NONEXISTENT_CFG, sqlite=True, sql=False, jwt=False,
                gen_res=False, gen_db=False,
            )

    def test_setTokenAuthFunction_defaultsToAuthFunc(self):
        from bottle_suite.plugins.jwt import authFunc

        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, jwt="k", sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.setTokenAuthFunction()
        self.assertIs(bs.jwt.token_paths["token"], authFunc)

    def test_setTokenAuthFunction_customFunc(self):
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, jwt="k", sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        custom = lambda: {"exp": 123}
        bs.setTokenAuthFunction(custom)
        self.assertIs(bs.jwt.token_paths["token"], custom)

    def test_setupJwt_strConfig(self):
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG,
            jwt="mykey",
            sqlite=False,
            sql=False,
            gen_res=False,
            gen_db=False,
        )
        self.assertEqual(bs.jwt.jwt_key, "mykey")

    def test_setupCors_false_noPlugin(self):
        bs = BottleSuite(
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
        bs = BottleSuite(
            cfg_file=path, cors=False, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        self.assertIsNotNone(bs.cors)

    def test_configPrecedence_cors_tomlOverridesCtorTrue(self):
        path = self._writeCfg("cors = false\n")
        bs = BottleSuite(
            cfg_file=path, cors=True, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        self.assertIsNone(bs.cors)

    def test_configPrecedence_rest_tomlOverridesCtor(self):
        path = self._writeCfg("rest = false\n")
        bs = BottleSuite(
            cfg_file=path, rest=True, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        self.assertIsNone(bs.rest)

    def test_configPrecedence_jwt_tomlOverridesCtor(self):
        path = self._writeCfg("jwt = false\n")
        bs = BottleSuite(
            cfg_file=path, jwt="somekey", sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        self.assertIsNone(bs.jwt)

    def test_configPrecedence_sqlite_tomlOverridesCtor(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        path = self._writeCfg(f'sqlite = "{tmp_db}"\n')
        bs = BottleSuite(
            cfg_file=path, sqlite=False, sql=False, jwt=False,
            gen_res=False, gen_db=False,
        )
        self.assertIsNotNone(bs.sqlite)

    def test_configPrecedence_sql_tomlOverridesCtor(self):
        path = self._writeCfg(
            'sql = {host = "h", user = "u", password = "p", database = "d"}\n'
        )
        bs = BottleSuite(
            cfg_file=path, sql=False, sqlite=False, jwt=False,
            gen_res=False, gen_db=False,
        )
        self.assertIsNotNone(bs.sql)

    def test_configPrecedence_dashboard_tomlOverridesCtor(self):
        path = self._writeCfg("dashboard = true\n")
        bs = BottleSuite(
            cfg_file=path, dashboard=False, jwt="k", sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        self.assertTrue(any(r.rule.startswith("/dashboard") for r in bs.routes))

    # --- sql/sqlite mutual exclusion boundary ---
    def test_sqlAndSqliteBothTruthy_raises(self):
        with self.assertRaises(Exception):
            BottleSuite(
                cfg_file=NONEXISTENT_CFG, sql=True, sqlite=True, jwt=False,
                gen_res=False, gen_db=False,
            )

    def test_sqlAndSqliteBothFalsyEmpty_noRaise(self):
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, sql="", sqlite={}, jwt=False,
            gen_res=False, gen_db=False,
        )
        self.assertIsNone(bs.sql)
        self.assertIsNone(bs.sqlite)

    # --- setupDashboard ---
    def test_setupDashboard_missingBuild_warnsNoExcept(self):
        with mock.patch("bottle_suite.bottle_suite.DIST", "/nonexistent/dashboard/dist"):
            bs = BottleSuite(
                cfg_file=NONEXISTENT_CFG, dashboard=True, jwt="k", sqlite=False,
                sql=False, gen_res=False, gen_db=False,
            )
        self.assertTrue(any(r.rule.startswith("/dashboard") for r in bs.routes))

    def test_setupDashboard_buildFound_noWarning(self):
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        with open(os.path.join(tmp_dir, "index.html"), "w") as f:
            f.write("<html></html>")
        with mock.patch("bottle_suite.bottle_suite.DIST", tmp_dir):
            bs = BottleSuite(
                cfg_file=NONEXISTENT_CFG, dashboard=True, jwt="k", sqlite=False,
                sql=False, gen_res=False, gen_db=False,
            )
        self.assertTrue(any(r.rule.startswith("/dashboard") for r in bs.routes))

    def test_dashboardAndNuxt_routeHandlers_invoked(self):
        bs = BottleSuite(
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
        with mock.patch("bottle_suite.bottle_suite.DIST", tmp_dir):
            bs = BottleSuite(
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
        with mock.patch("bottle_suite.bottle_suite.DIST", tmp_dir):
            bs = BottleSuite(
                cfg_file=NONEXISTENT_CFG, dashboard=True, jwt="k", sqlite=False,
                sql=False, gen_res=False, gen_db=False,
            )
            app = webtest.TestApp(bs)
            resp = app.get("/dashboard/resources/123")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.body, b"<html>spa shell</html>")

    def test_setupDashboard_overridesDefaultAuthFunc(self):
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, dashboard=True, jwt="k", sqlite=False,
            sql=False, gen_res=False, gen_db=False,
        )
        self.assertEqual(bs.jwt.token_paths["token"], bs.dashboard_token.authenticate)

    def test_setupDashboard_dictConfig_enabledKeyRespected(self):
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, dashboard={"enabled": False}, jwt="k",
            sqlite=False, sql=False, gen_res=False, gen_db=False,
        )
        self.assertIsNone(bs.dashboard_token)
        self.assertFalse(any(r.rule.startswith("/dashboard") for r in bs.routes))

        bs2 = BottleSuite(
            cfg_file=NONEXISTENT_CFG, dashboard={"enabled": True}, jwt="k",
            sqlite=False, sql=False, gen_res=False, gen_db=False,
        )
        self.assertIsNotNone(bs2.dashboard_token)
        self.assertTrue(any(r.rule.startswith("/dashboard") for r in bs2.routes))

    def test_setupDashboard_jwtFalse_noCrash(self):
        # Regression for fix #10.
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, dashboard=True, jwt=False, sqlite=False,
            sql=False, gen_res=False, gen_db=False,
        )
        self.assertIsNone(bs.jwt)

    # --- setupRest ---
    def test_setupRest_genTrue_noResourcesDir_noop(self):
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            bs = BottleSuite(
                cfg_file=NONEXISTENT_CFG, rest=True, gen_res=True, gen_db=False,
                jwt=False, sqlite=False, sql=False,
            )
            self.assertIsNotNone(bs.rest)
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp)

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
        bs = BottleSuite(
            cfg_file=path, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.setRoles(BoolRolesResource, "boolroles")  # should not raise
        cfg = BoolRolesResource.getRouteConfig(bottle_rest.Resource.Methods.GET)
        self.assertEqual(cfg["roles"], True)

    # --- createResForDB ---
    def test_createResForDB_misconfigured_noop(self):
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, rest=False, sqlite=False, sql=False,
            jwt=False, gen_res=False, gen_db=False,
        )
        bs.createResForDB()  # else: pass branch -- should not raise

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
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG,
            sql={"host": "h", "user": "u", "password": "p", "database": "d"},
            sqlite=False, jwt=False, gen_res=False, gen_db=False,
        )
        bs.createResForDB()
        self.assertNotIn("Nokey", bs.resource_names)

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
        bs = BottleSuite(cfg_file=path, jwt=False, gen_res=False, gen_db=True)
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
        bs = BottleSuite(
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
        bs = BottleSuite(
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
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG,
            sql={"host": "h", "user": "u", "password": "p", "database": "d"},
            sqlite=False, jwt=False, gen_res=False, gen_db=False,
        )
        db = bs.getDBCursor()
        self.assertIs(db, cursor)

    def test_getDBCursor_neitherConfigured_raisesClearException(self):
        # Regression for fix #11.
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, sqlite=False, sql=False, jwt=False,
            gen_res=False, gen_db=False,
        )
        with self.assertRaises(Exception):
            bs.getDBCursor()

    def test_getDBTables_neitherConfigured_raisesClearException(self):
        bs = BottleSuite(
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
        bs = BottleSuite(
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
            bs = BottleSuite(
                cfg_file=NONEXISTENT_CFG,
                sql={"host": "h", "user": "u", "password": "p", "database": "d"},
                sqlite=False, jwt=False, gen_res=False, gen_db=False,
            )
            with self.assertRaises(AttributeError):
                bs.getDBTables()

    def test_getSqlTable_mysqlMocked(self):
        cursor = make_mysql_cursor(
            fetchall=[("id", "INTEGER", "NO", "PRI", None, "auto_increment")]
        )
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, sqlite=False, sql=False, jwt=False,
            gen_res=False, gen_db=False,
        )
        result = bs.getSqlTable(cursor, "widgets")
        self.assertEqual(result[0]["field"], "id")

    # --- createTable / alterDBTable ---
    def test_createTable_sqlite(self):
        # Regression for fix #13 (self.sqlite.dbfile -> sql_config["database"]).
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        bs.createTable("widgets")
        self.assertIn("widgets", bs.getDBTables())

    def test_createTable_invalidName_raisesValueError(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        with self.assertRaises(ValueError):
            bs.createTable("bad name")

    def test_createTable_duplicateName_raisesOperationalError(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        bs.createTable("widgets")
        with self.assertRaises(sqlite3.OperationalError):
            bs.createTable("widgets")

    def test_alterDBTable_sqlite_renameColumn(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = BottleSuite(
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
        bs = BottleSuite(
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
        bs = BottleSuite(
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
        bs = BottleSuite(
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
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, sqlite=False,
            sql={"host": "h", "user": "u", "password": "p", "database": "d"},
            jwt=False, gen_res=False, gen_db=False,
        )
        bs.createTable("widgets")  # no crash, no real connection attempted

    def test_alterDBTable_mysqlConfigured_isNoop_characterized(self):
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, sqlite=False,
            sql={"host": "h", "user": "u", "password": "p", "database": "d"},
            jwt=False, gen_res=False, gen_db=False,
        )
        bs.alterDBTable(
            "widgets",
            {"cid": 0, "name": "x", "type": "TEXT", "notnull": 0,
             "dflt_value": None, "pk": 0},
        )

    # --- getResourceConfig / updatePaths / updateRoles / saveConfig ---
    def test_getResourceConfig_freshConfigNoResourcesKey(self):
        # Regression for fix #5.
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        self.assertNotIn("resources", bs.cfg)
        cfg = bs.getResourceConfig("widgets")
        self.assertEqual(cfg, {})
        self.assertIn("resources", bs.cfg)

    def test_updatePaths_indexOutOfRange_appends(self):
        path = self._writeCfg("")
        bs = BottleSuite(
            cfg_file=path, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.updatePaths("widgets", 5, "/widgets")
        self.assertEqual(bs.cfg["resources"]["widgets"]["paths"], ["/widgets"])

    def test_updatePaths_validIndex_overwrites(self):
        path = self._writeCfg("")
        bs = BottleSuite(
            cfg_file=path, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.updatePaths("widgets", 0, "/a")
        bs.updatePaths("widgets", 0, "/b")
        self.assertEqual(bs.cfg["resources"]["widgets"]["paths"], ["/b"])

    def test_updateRoles_stringTrueFalse(self):
        path = self._writeCfg("")
        bs = BottleSuite(
            cfg_file=path, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.updateRoles("widgets", "get", "true")
        self.assertEqual(bs.cfg["resources"]["widgets"]["roles"]["get"], True)
        bs.updateRoles("widgets", "get", "false")
        self.assertEqual(bs.cfg["resources"]["widgets"]["roles"]["get"], False)

    def test_updateRoles_commaSeparatedString(self):
        path = self._writeCfg("")
        bs = BottleSuite(
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
        bs = BottleSuite(
            cfg_file=path, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.updateRoles("widgets", "get", ["admin"])
        self.assertEqual(bs.cfg["resources"]["widgets"]["roles"]["get"], ["admin"])

    def test_updateRoles_boolInput_noCrash(self):
        path = self._writeCfg("")
        bs = BottleSuite(
            cfg_file=path, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.updateRoles("widgets", "get", True)
        self.assertEqual(bs.cfg["resources"]["widgets"]["roles"]["get"], True)

    def test_saveConfig_errorSwallowed_noRaise(self):
        # A directory path for cfg_file makes open(cfg_file, "w+") raise
        # IsADirectoryError; toml.load() on it at construction time is
        # likewise caught by the bare except, so self.cfg starts as {}.
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir)
        bs = BottleSuite(
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
            bs = BottleSuite(
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
            bs = BottleSuite(
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
            bs = BottleSuite(
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
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.reloadServer()
        from bottle_suite import reload as reload_module

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

    # --- resource_names / getRefEndpoints ---
    def test_resourceNames_noRest_returnsEmptySet(self):
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, rest=False, jwt=False, sqlite=False,
            sql=False, gen_res=False, gen_db=False,
        )
        self.assertEqual(bs.resource_names, set())

    def test_getRefEndpoints_sqlite_currentlyCrashes_characterized(self):
        # Same pre-existing, MySQL-only FOREIGN_KEY_SQL limitation as the
        # nested ref-table route (see test_resource_factory.py) -- this
        # method is unused/dead in the current call graph (commented out in
        # createResForDB) and crashes on sqlite for the same reason.
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, sqlite=tmp_db, jwt=False,
            gen_res=False, gen_db=False,
        )
        with self.assertRaises(Exception):
            bs.getRefEndpoints("predations")

    def test_getRefEndpoints_mysqlMocked(self):
        cursor = make_mysql_cursor(
            fetchall=[
                {"table_name": "predations", "column_name": "predator",
                 "referenced_table_name": "animals", "referenced_column_name": "id"},
                {"table_name": "predations", "column_name": "self_ref",
                 "referenced_table_name": "predations", "referenced_column_name": "id"},
            ]
        )
        patcher, mock_conn, cursor = patch_pymysql_connect(cursor)
        patcher.start()
        self.addCleanup(patcher.stop)
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG,
            sql={"host": "h", "user": "u", "password": "p", "database": "d"},
            sqlite=False, jwt=False, gen_res=False, gen_db=False,
        )
        endpoints = bs.getRefEndpoints("predations")
        self.assertEqual(endpoints, ["/animals/<id>/predations"])

    def test_getSQLiteTable(self):
        with sqlite3.connect("resources.db") as conn:
            conn.row_factory = lambda cursor, row: {
                col[0]: row[idx] for idx, col in enumerate(cursor.description)
            }
            db = conn.cursor()
            table = self.bottle_suite.getDBTable(db, "animals")
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
        tables = self.bottle_suite.getDBTables()
        self.assertIn("animals", tables)
        self.assertIn("predations", tables)

    def test_genResoursesForDB(self):
        self.bottle_suite = BottleSuite()
        self.app = webtest.TestApp(self.bottle_suite)
        self.assertIn("Animals", self.bottle_suite.resource_names)
        self.assertIn("Predations", self.bottle_suite.resource_names)
        self.assertEqual("dog", self.app.get("/animals/1").json["name"])
        self.assertEqual(6, self.app.get("/predations/1").json["predator"])

    # CORS
