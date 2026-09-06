import _paths  # noqa: F401
import unittest
from unittest import mock
import os
import tempfile
import types
import webtest
import jwt as pyjwt
from datetime import datetime, timedelta
from bottle_suite import BottleSuite
from bottle_suite import openapi
import db_fixtures
from mysql_mock import make_mysql_cursor, patch_pymysql_connect

NONEXISTENT_CFG = "no_such_bottle_suite_cfg.toml"
JWT_KEY = "secret"


def _write_cfg(content):
    fd, path = tempfile.mkstemp(suffix=".toml", dir=os.getcwd())
    os.close(fd)
    with open(path, "w") as f:
        f.write(content)
    return path


def _valid_token(**extra):
    payload = {"exp": datetime.utcnow() + timedelta(days=1), **extra}
    return pyjwt.encode(payload, JWT_KEY, algorithm="HS256")


class TestOpenApiToggle(unittest.TestCase):
    """Covers BottleSuite.setupOpenApi's wiring in bottle_suite.py."""

    def test_default_enabled_returns200(self):
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        app = webtest.TestApp(bs)
        resp = app.get("/openapi.json")
        self.assertEqual(resp.status_code, 200)
        for key in ("openapi", "info", "paths"):
            self.assertIn(key, resp.json)

    def test_disabledBool_notRegistered(self):
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False, openapi=False,
        )
        app = webtest.TestApp(bs)
        resp = app.get("/openapi.json", expect_errors=True)
        self.assertEqual(resp.status_code, 404)

    def test_disabledDict_notRegistered(self):
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False, openapi={"enabled": False},
        )
        app = webtest.TestApp(bs)
        resp = app.get("/openapi.json", expect_errors=True)
        self.assertEqual(resp.status_code, 404)

    def test_tomlOverridesConstructorArg(self):
        path = _write_cfg("openapi = false\n")
        self.addCleanup(os.remove, path)
        bs = BottleSuite(cfg_file=path, jwt=False, sqlite=False, sql=False,
                          gen_res=False, gen_db=False, openapi=True)
        app = webtest.TestApp(bs)
        resp = app.get("/openapi.json", expect_errors=True)
        self.assertEqual(resp.status_code, 404)

    def test_rolesGated_requiresAuth(self):
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, jwt={"jwt_key": JWT_KEY}, sqlite=False,
            sql=False, gen_res=False, gen_db=False,
            openapi={"roles": ["admin"]},
        )
        app = webtest.TestApp(bs)
        resp = app.get("/openapi.json", expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        token = _valid_token(roles=["admin"])
        resp = app.get(
            "/openapi.json", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(resp.status_code, 200)


class TestBuildSpecHelpers(unittest.TestCase):
    """Direct unit tests of openapi.py's private helpers."""

    def test_mapSqlType_known(self):
        self.assertEqual(openapi._mapSqlType("VARCHAR(255)"), {"type": "string"})
        self.assertEqual(openapi._mapSqlType("INTEGER"), {"type": "integer"})

    def test_mapSqlType_unknown_fallsBackToString(self):
        self.assertEqual(openapi._mapSqlType("FROBNICATE"), {"type": "string"})

    def test_mapSqlType_none_fallsBackToString(self):
        self.assertEqual(openapi._mapSqlType(None), {"type": "string"})

    def test_pathParams_extractsNames(self):
        self.assertEqual(
            openapi._pathParams("/animals/<key>"),
            [{"name": "key", "in": "path", "required": True, "schema": {"type": "string"}}],
        )
        self.assertEqual(openapi._pathParams("/animals"), [])

    def test_tag_authRuleWinsOverResource(self):
        fake_resource = types.SimpleNamespace(name="DashboardToken")
        self.assertEqual(openapi._tag(fake_resource, "/token"), "Auth")
        self.assertEqual(openapi._tag(None, "/users/current"), "Auth")

    def test_tag_resourceName(self):
        resource = types.SimpleNamespace(name="Widgets")
        self.assertEqual(openapi._tag(resource, "/widgets"), "Widgets")

    def test_tag_defaultFallback(self):
        self.assertEqual(openapi._tag(None, "/plain"), "default")

    def test_tableSchemaRef_requiredFieldDetection_andCaching(self):
        resource = types.SimpleNamespace(name="Widgets", table="widgets")
        fields = [
            {"name": "id", "type": "INTEGER", "notnull": True, "default": None, "key": 1},
            {"name": "email", "type": "VARCHAR(255)", "notnull": True, "default": None, "key": 0},
            {"name": "nickname", "type": "TEXT", "notnull": False, "default": None, "key": 0},
            {"name": "role", "type": "TEXT", "notnull": True, "default": "user", "key": 0},
        ]
        schemas = {}
        name = openapi._tableSchemaRef(schemas, resource, fields)
        self.assertEqual(name, "Widgets")
        self.assertEqual(schemas["Widgets"]["required"], ["email"])
        # Second call for the same resource must hit the cache branch and
        # not rebuild from (now empty) fields.
        openapi._tableSchemaRef(schemas, resource, [])
        self.assertIn("email", schemas["Widgets"]["properties"])

    def test_tableSchemaRef_noRequiredFields_omitsKey(self):
        resource = types.SimpleNamespace(name="Notes", table="notes")
        fields = [{"name": "body", "type": "TEXT", "notnull": False, "default": None, "key": 0}]
        schemas = {}
        openapi._tableSchemaRef(schemas, resource, fields)
        self.assertNotIn("required", schemas["Notes"])

    def test_paramSchema_skipsAndRequired(self):
        def cb(name, nickname="anon", *args, **kwargs):
            pass

        schema = openapi._paramSchema(cb, skip=set())
        self.assertEqual(set(schema["properties"]), {"name", "nickname"})
        self.assertEqual(schema["required"], ["name"])

    def test_paramSchema_allOptional_omitsRequiredKey(self):
        def cb(nickname="anon"):
            pass

        schema = openapi._paramSchema(cb, skip=set())
        self.assertNotIn("required", schema)

    def test_paramSchema_skipSet(self):
        def cb(db, key, name):
            pass

        schema = openapi._paramSchema(cb, skip={"db", "key"})
        self.assertEqual(set(schema["properties"]), {"name"})

    def test_paramSchema_intDefault_inferredInteger(self):
        def cb(qty=1):
            pass

        schema = openapi._paramSchema(cb, skip=set())
        self.assertEqual(schema["properties"]["qty"], {"type": "integer"})

    def test_paramSchema_floatDefault_inferredNumber(self):
        def cb(price=1.5):
            pass

        schema = openapi._paramSchema(cb, skip=set())
        self.assertEqual(schema["properties"]["price"], {"type": "number"})

    def test_paramSchema_boolDefault_inferredBoolean_notInteger(self):
        def cb(active=True):
            pass

        schema = openapi._paramSchema(cb, skip=set())
        self.assertEqual(schema["properties"]["active"], {"type": "boolean"})

    def test_paramSchema_noneDefault_fallsBackToString(self):
        def cb(nickname=None):
            pass

        schema = openapi._paramSchema(cb, skip=set())
        self.assertEqual(schema["properties"]["nickname"], {"type": "string"})

    def test_paramSchema_unknownDefaultType_fallsBackToString(self):
        def cb(tags=[]):
            pass

        schema = openapi._paramSchema(cb, skip=set())
        self.assertEqual(schema["properties"]["tags"], {"type": "string"})

    def test_infoBlock_defaults(self):
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        info = openapi._infoBlock(bs)
        self.assertEqual(info["title"], "Bottle Suite API")
        self.assertIn("version", info)

    def test_infoBlock_tomlOverrides(self):
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.cfg["openapi"] = {"title": "Custom", "version": "9.9.9", "description": "desc"}
        info = openapi._infoBlock(bs)
        self.assertEqual(info, {"title": "Custom", "version": "9.9.9", "description": "desc"})

    def test_infoBlock_openapiCfgNotDict_ignored(self):
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        bs.cfg["openapi"] = True
        info = openapi._infoBlock(bs)
        self.assertEqual(info["title"], "Bottle Suite API")

    def test_infoBlock_packageNotFound_fallsBackVersion(self):
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        with mock.patch.object(
            openapi, "_pkg_version", side_effect=openapi.PackageNotFoundError
        ):
            info = openapi._infoBlock(bs)
        self.assertEqual(info["version"], "0.0.0")


class TestBuildSpecIntegration(unittest.TestCase):
    """Full-app tests: sqlite fixture DB (animals/predations), a hand-written
    Python resource (FileResource), JWT + dashboard auth endpoints."""

    def setUp(self):
        self.tmp_db = db_fixtures.temp_sqlite_copy()
        self.bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG,
            jwt={"jwt_key": JWT_KEY},
            sqlite=self.tmp_db,
            sql=False,
            dashboard=True,
            gen_res=True,
            gen_db=True,
        )
        self.spec = openapi.buildSpec(self.bs)
        self.paths = self.spec["paths"]

    def tearDown(self):
        os.remove(self.tmp_db)

    def test_dbResourcePaths_present(self):
        self.assertIn("/animals", self.paths)
        self.assertIn("/animals/<key>", self.paths)
        self.assertIn("/predations", self.paths)

    def test_pythonResourcePath_present(self):
        self.assertIn("/file_resource", self.paths)
        self.assertIn("get", self.paths["/file_resource"])
        self.assertIn("post", self.paths["/file_resource"])

    def test_pythonResource_noParams_noRequestBody(self):
        self.assertNotIn("requestBody", self.paths["/file_resource"]["post"])

    def test_authEndpoints_present_taggedAuth(self):
        self.assertIn("/token", self.paths)
        self.assertIn("/users/current", self.paths)
        self.assertEqual(self.paths["/token"]["post"]["tags"], ["Auth"])
        self.assertEqual(self.paths["/users/current"]["get"]["tags"], ["Auth"])

    def test_metaAndDashboardRoutes_excluded(self):
        for rule in (
            "/_resources", "/_datatypes", "/bottle_suite_cfg",
            "/_python_resources", "/dashboard", "/openapi.json",
        ):
            self.assertNotIn(rule, self.paths)

    def test_dbResourceTag_isResourceName(self):
        self.assertEqual(self.paths["/animals"]["get"]["tags"], ["Animals"])

    def test_dbSchema_registeredInComponents(self):
        schemas = self.spec["components"]["schemas"]
        self.assertIn("Animals", schemas)
        self.assertEqual(set(schemas["Animals"]["properties"]), {"id", "name"})

    def test_get_list_wrapsArrayUnderTableName(self):
        schema = self.paths["/animals"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(schema["properties"]["animals"]["type"], "array")

    def test_get_byKey_returnsItemRefDirectly(self):
        schema = self.paths["/animals/<key>"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertIn("$ref", schema)

    def test_post_hasRequestBodyAnd201(self):
        op = self.paths["/animals"]["post"]
        self.assertIn("requestBody", op)
        self.assertIn("201", op["responses"])

    def test_put_hasRequestBodyAnd200(self):
        op = self.paths["/animals/<key>"]["put"]
        self.assertIn("requestBody", op)
        self.assertIn("200", op["responses"])

    def test_patch_requestBody_omitsRequired(self):
        op = self.paths["/animals/<key>"]["patch"]
        body = op["requestBody"]["content"]["application/json"]["schema"]
        self.assertNotIn("required", body)

    def test_delete_hasNoRequestBody(self):
        op = self.paths["/animals/<key>"]["delete"]
        self.assertNotIn("requestBody", op)
        self.assertIn("200", op["responses"])

    def test_pathParam_documented(self):
        params = self.paths["/animals/<key>"]["get"]["parameters"]
        self.assertEqual(params, [{"name": "key", "in": "path", "required": True, "schema": {"type": "string"}}])

    def test_nonRolesRoute_noSecurity(self):
        self.assertNotIn("security", self.paths["/animals"]["get"])


class TestBuildSpecSecurityAndComponents(unittest.TestCase):
    def _bareApp(self, jwt=False):
        return BottleSuite(
            cfg_file=NONEXISTENT_CFG, jwt=jwt, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )

    def test_rolesWithJwt_addsSecurityAndBearerScheme(self):
        bs = self._bareApp(jwt={"jwt_key": JWT_KEY})
        bs.route("/plain", "GET", lambda: {"ok": True}, roles=["admin"])
        spec = openapi.buildSpec(bs)
        self.assertEqual(spec["paths"]["/plain"]["get"]["security"], [{"bearerAuth": []}])
        self.assertIn("securitySchemes", spec["components"])
        self.assertNotIn("schemas", spec["components"])
        self.assertEqual(spec["paths"]["/plain"]["get"]["tags"], ["default"])

    def test_rolesWithoutJwt_noSecurity(self):
        bs = self._bareApp(jwt=False)
        bs.route("/plain", "GET", lambda: {"ok": True}, roles=["admin"])
        spec = openapi.buildSpec(bs)
        self.assertNotIn("security", spec["paths"]["/plain"]["get"])
        self.assertNotIn("components", spec)

    def test_plainRoute_requiredParam_addsRequestBody(self):
        bs = self._bareApp(jwt=False)
        bs.route("/plain", "POST", lambda required_field: {"ok": True})
        spec = openapi.buildSpec(bs)
        body = spec["paths"]["/plain"]["post"]["requestBody"]["content"]["application/json"]["schema"]
        self.assertEqual(body["required"], ["required_field"])

    def test_plainRoute_varargsAndKwargs_skipped(self):
        bs = self._bareApp(jwt=False)
        bs.route("/varargs", "POST", lambda *args, **kwargs: {"ok": True})
        spec = openapi.buildSpec(bs)
        self.assertNotIn("requestBody", spec["paths"]["/varargs"]["post"])

    def test_noDbNoRoutes_noComponentsKey(self):
        bs = self._bareApp(jwt=False)
        spec = openapi.buildSpec(bs)
        self.assertEqual(spec["paths"], {})
        self.assertNotIn("components", spec)


class TestBuildSpecMysql(unittest.TestCase):
    def test_mysqlBackedTable_typeMappingAndSchema(self):
        cursor = make_mysql_cursor()
        patcher, mock_conn, cursor = patch_pymysql_connect(cursor)
        patcher.start()
        self.addCleanup(patcher.stop)

        table_list = [{"name": "widgets"}]
        columns = [
            {"Field": "id", "Type": "INT", "Null": "NO", "Default": None, "Key": "PRI"},
            {"Field": "label", "Type": "VARCHAR(45)", "Null": "NO", "Default": None, "Key": ""},
        ]
        cursor.fetchall.side_effect = [table_list, columns]
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG,
            sql={"host": "h", "user": "u", "password": "p", "database": "d"},
            sqlite=False, jwt=False, gen_res=False, gen_db=True,
        )
        # Reset the mock's fetchall sequence for the getDBTables() call that
        # buildSpec makes on its own (separate from the one createResForDB
        # already consumed above).
        cursor.fetchall.side_effect = [table_list, columns]
        spec = openapi.buildSpec(bs)
        schema = spec["components"]["schemas"]["Widgets"]
        self.assertEqual(schema["properties"]["id"], {"type": "integer"})
        self.assertEqual(schema["properties"]["label"], {"type": "string"})


if __name__ == "__main__":
    unittest.main()
