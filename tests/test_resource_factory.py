import _paths  # noqa: F401
import unittest
import os
import inspect
import sqlite3
import webtest
import pymysql
import bottle
from bottle_suite import BottleSuite, resource_factory
from bottle_suite.resource_factory import PatchData
import db_fixtures
from mysql_mock import make_mysql_cursor, patch_pymysql_connect

NONEXISTENT_CFG = "no_such_bottle_suite_cfg.toml"


class TestResourceFactorySqlite(unittest.TestCase):
    """Exercises the generated resources against a real, throwaway sqlite
    copy of tests/resources.db -- tests/resources.db itself is never
    mutated."""

    def setUp(self):
        self.tmp_db = db_fixtures.temp_sqlite_copy()
        self.bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG,
            cors=True,
            rest=True,
            jwt=False,
            sqlite=self.tmp_db,
            sql=False,
            gen_res=False,
            gen_db=True,
        )
        self.app = webtest.TestApp(self.bs)

    def tearDown(self):
        os.remove(self.tmp_db)

    # --- fix #1: multi-filter GET produced invalid SQL ---
    def test_get_singleFilter(self):
        resp = self.app.get("/animals", {"name": "dog"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json["animals"]), 1)

    def test_get_multipleQueryFilters_validSql(self):
        resp = self.app.get("/animals", {"name": "dog", "id": "1"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json["animals"]), 1)
        self.assertEqual(resp.json["animals"][0]["name"], "dog")

    def test_get_byKey_found(self):
        resp = self.app.get("/animals/1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json["name"], "dog")

    def test_get_byKey_notFound(self):
        resp = self.app.get("/animals/999", expect_errors=True)
        self.assertEqual(resp.status_code, 404)

    def test_get_list_empty(self):
        resp = self.app.get("/animals", {"name": "nonexistent-animal"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json["animals"], [])

    # --- getRefs: default levels=1 does not nest ---
    def test_getRefs_levels1_noNesting(self):
        resp = self.app.get("/predations/1")
        self.assertEqual(resp.status_code, 200)
        # Raw FK column values, not nested objects, at the default level.
        self.assertEqual(resp.json["predator"], 6)
        self.assertEqual(resp.json["prey"], 5)

    # --- getRefs: levels>=2 engages nesting. FK metadata is pre-seeded here
    # to isolate and exercise the row-nesting logic itself (regression for
    # fix #2 and the set-vs-tuple binding bug fixed alongside it) separately
    # from the real sqlite PRAGMA-based discovery, which is covered by
    # test_getRefs_levels2_nestingEngages_sqlite_realDiscovery below.
    def test_getRefs_levels2_nestingEngages_sqlite(self):
        predations_resource = next(
            r for r in self.bs.rest.resources if r.name == "Predations"
        )
        predations_cls = type(predations_resource)
        predations_cls.refs["predations"] = [
            {
                "table_name": "predations",
                "column_name": "predator",
                "referenced_table_name": "animals",
                "referenced_column_name": "id",
            },
            {
                "table_name": "predations",
                "column_name": "prey",
                "referenced_table_name": "animals",
                "referenced_column_name": "id",
            },
        ]
        resp = self.app.get("/predations/1", {"levels": "2"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json["predator"]["name"], "wolf")
        self.assertEqual(resp.json["prey"]["name"], "rabbit")

    # --- getRefs: real FK discovery via PRAGMA foreign_key_list, no
    # pre-seeded cache. Regression test for the sqlite branch added to
    # getRefs() -- previously this path unconditionally ran the MySQL-only
    # FOREIGN_KEY_SQL query and crashed with
    # "sqlite3.OperationalError: no such table: information_schema...".
    def test_getRefs_levels2_nestingEngages_sqlite_realDiscovery(self):
        resp = self.app.get("/predations/1", {"levels": "2"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json["predator"]["name"], "wolf")
        self.assertEqual(resp.json["prey"]["name"], "rabbit")

    def test_getRefs_noForeignKeys_sqlite_returnsEmptyList(self):
        # A table with no FKs still needs to resolve to an empty ref list
        # (rather than crashing) via the same PRAGMA-based discovery.
        resp = self.app.get("/animals/1", {"levels": "2"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json["name"], "dog")

    # --- nested /<ref_table>/<ref_id>/<table> route on sqlite: previously
    # crashed because getRefs() unconditionally ran the MySQL-only
    # FOREIGN_KEY_SQL discovery query for this branch (row=None); now uses
    # PRAGMA foreign_key_list and correctly filters the child table by its
    # own FK column (not the parent's referenced column -- a separate,
    # pre-existing bug fixed alongside the crash). "predations" has *two*
    # FKs to "animals" (predator, prey); get()'s next(...) match-by-table
    # lookup is inherently ambiguous in that case and always resolves to
    # the first FK found (here: "prey") -- a separate, pre-existing
    # limitation, not something this fix attempts to resolve. So id=5
    # (the prey animal) resolves correctly; id=6 (predator) would not.
    def test_nestedRefTableRefId_sqlite_returnsMatchingRow(self):
        resp = self.app.get("/animals/5/predations")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json["predations"]), 1)
        self.assertEqual(resp.json["predations"][0]["id"], 1)

    # --- POST / IntegrityError handling ---
    def test_post_creates_andReturnsCreatedRow(self):
        resp = self.app.post_json("/animals", {"name": "elephant"})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json["name"], "elephant")

    def test_post_integrityError_sqlite_uniqueMessage(self):
        db = self.bs.getDBCursor()
        db.execute(
            "CREATE TABLE uniques (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)"
        )
        db.execute("INSERT INTO uniques (name) VALUES ('a')")
        fields = self.bs.getDBTable(db, "uniques")
        Resource = resource_factory.createResource("uniques", fields)
        resource = Resource()
        result = resource.post(db, name="a")
        self.assertEqual(bottle.response.status_code, 422)
        self.assertIn("must be unique", result["message"])

    def test_post_integrityError_sqlite_checkConstraint_noIndexError(self):
        # Regression for fix #4: a CHECK-constraint message has no dot,
        # which used to crash with an unhandled IndexError.
        db = self.bs.getDBCursor()
        db.execute(
            "CREATE TABLE checked (id INTEGER PRIMARY KEY AUTOINCREMENT, qty INTEGER CHECK(qty > 0))"
        )
        fields = self.bs.getDBTable(db, "checked")
        Resource = resource_factory.createResource("checked", fields)
        resource = Resource()
        result = resource.post(db, qty=-1)
        self.assertEqual(bottle.response.status_code, 422)
        self.assertIn("message", result)

    # --- PATCH / PUT via HTTP: the generated route uses the literal URL
    # param name "<key>" (bottle_suite.py::createResForDB), while
    # createFunction() generates put/patch signatures using the *actual*
    # primary-key field name (e.g. "id"). createFunction()'s key_param
    # mechanism renames the outer param to "key" (matching the route) and
    # maps it back to the real column name for the internal _doPut/_doPatch
    # call, so this now reaches the handlers instead of 400ing beforehand.
    def test_patch_viaHttp_updatesField(self):
        resp = self.app.patch_json("/animals/2", {"name": "housecat"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json["name"], "housecat")

    def test_put_viaHttp_replacesRow(self):
        resp = self.app.put_json("/animals/1", {"name": "x"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json["name"], "x")

    # --- the underlying generated patch/put methods, called directly
    # (bypassing the broken URL-routing layer above) so their own logic is
    # still covered. ---
    def test_patch_updatesFields_directCall(self):
        animals = next(r for r in self.bs.rest.resources if r.name == "Animals")
        db = self.bs.getDBCursor()
        # "key" (not "id") is now the correct outer kwarg -- createFunction's
        # key_param mechanism maps it to the real column name internally.
        result = animals.patch(db, key=2, name="housecat")
        self.assertEqual(bottle.response.status_code, 200)
        self.assertEqual(result["name"], "housecat")

    def test_patch_allFieldsUnchanged_500Characterized_directCall(self):
        # Characterization: an empty SET clause is invalid SQL; the broad
        # except in _doPatch turns that into a 500 rather than a no-op.
        animals = next(r for r in self.bs.rest.resources if r.name == "Animals")
        db = self.bs.getDBCursor()
        result = animals.patch(db, key=2)
        self.assertEqual(bottle.response.status_code, 500)
        self.assertIn("message", result)

    def test_put_replacesFields_directCall(self):
        animals = next(r for r in self.bs.rest.resources if r.name == "Animals")
        db = self.bs.getDBCursor()
        # "key" (not "id") is now the correct outer kwarg -- createFunction's
        # key_param mechanism maps it to the real column name internally.
        result = animals.put(db, key=1, name="x")
        self.assertEqual(bottle.response.status_code, 200)
        self.assertEqual(result["name"], "x")

    def test_delete_removesRow_viaHttp(self):
        resp = self.app.delete("/animals/1")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("message", resp.json)
        self.assertEqual(
            self.app.get("/animals/1", expect_errors=True).status_code, 404
        )

    def test_options_isNoop(self):
        resp = self.app.options("/animals")
        self.assertEqual(resp.status_code, 200)


class TestCreateResourceDirect(unittest.TestCase):
    def test_createResource_noPrimaryKey_directCall_stillCrashes(self):
        # Direct misuse of the resource_factory API (bypassing the guarded
        # createResForDB() path added by fix #3) still crashes -- documents
        # that createResource() itself has no defensive check, by design.
        fields = [
            {"name": "name", "type": "TEXT", "notnull": False, "default": None, "key": 0}
        ]
        with self.assertRaises(TypeError):
            resource_factory.createResource("NoKey", fields)

    def test_createFunction_generatedSignatures(self):
        fields = [
            {"name": "id", "type": "INTEGER", "notnull": True, "default": None, "key": 1},
            {"name": "name", "type": "TEXT", "notnull": False, "default": None, "key": 0},
        ]
        Resource = resource_factory.createResource("things", fields)
        post_params = inspect.signature(Resource.post).parameters
        self.assertEqual(list(post_params), ["self", "db", "name", "id"])
        self.assertIsNone(post_params["id"].default)

        # put/patch expose the identity param as "key" (matching the
        # "/<table>/<key>" route), not the real column name "id" --
        # createFunction's key_param mechanism renames it in the outer
        # signature while still passing it through as "id" internally.
        patch_params = inspect.signature(Resource.patch).parameters
        self.assertEqual(list(patch_params), ["self", "db", "key", "name"])
        self.assertIs(patch_params["name"].default, PatchData.UNCHANGED)

        put_params = inspect.signature(Resource.put).parameters
        self.assertEqual(list(put_params), ["self", "db", "key", "name"])

    def test_createFunction_noPositionalArgs_keyOnlyTable(self):
        # A table with only the PK field has no non-key columns, so
        # createFunction("post", ...) is called with empty *args.
        fields = [
            {"name": "id", "type": "INTEGER", "notnull": True, "default": None, "key": 1},
        ]
        Resource = resource_factory.createResource("onlykey", fields)
        post_params = inspect.signature(Resource.post).parameters
        self.assertEqual(list(post_params), ["self", "db", "id"])

    def test_createFunction_putSignature_keyNotFirstInSchema(self):
        # PK declared last in the schema -- put's outer "key" param must
        # still map to the real column name by lookup, not by position.
        fields = [
            {"name": "name", "type": "TEXT", "notnull": False, "default": None, "key": 0},
            {"name": "id", "type": "INTEGER", "notnull": True, "default": None, "key": 1},
        ]
        Resource = resource_factory.createResource("things2", fields)
        put_params = inspect.signature(Resource.put).parameters
        self.assertEqual(list(put_params), ["self", "db", "name", "key"])


class TestResourceFactoryMysqlMocked(unittest.TestCase):
    """Exercises the MySQL-only branches directly against the generated
    resource, without going through BottleSuite's auto-discovery (which
    would require scripting many sequential mocked queries for table
    introspection) -- mocking pymysql.connect at the plugin/bottle_suite
    layer is covered separately in test_bottle_suite.py."""

    def setUp(self):
        self.fields = [
            {"name": "id", "type": "INTEGER", "notnull": True, "default": None, "key": 1},
            {"name": "name", "type": "TEXT", "notnull": False, "default": None, "key": 0},
        ]
        self.Resource = resource_factory.createResource("animals", self.fields, sql=True)
        self.resource = self.Resource()

    def test_bindChar_isPercentS(self):
        self.assertEqual(self.Resource.bind_char, "%s")

    def test_options_isNoop(self):
        self.assertIsNone(self.resource.options())

    def test_get_mysqlMocked_fetchallReturnsTuple(self):
        cursor = make_mysql_cursor(fetchall=({"id": 1, "name": "dog"},))
        result = self.resource.get(cursor)
        self.assertEqual(result, {"animals": [{"id": 1, "name": "dog"}]})

    def test_post_explicitTruthyKey_notPopped(self):
        cursor = make_mysql_cursor(lastrowid=99, fetchone={"id": 99, "name": "new"})
        result = self.resource.post(cursor, id=99, name="new")
        self.assertEqual(bottle.response.status_code, 201)
        self.assertEqual(result, {"id": 99, "name": "new"})

    def test_get_mysqlMocked_fallbackFetchPath(self):
        # execute() returning an int (real pymysql/DBAPI semantics) forces
        # the `except: rows = db.fetchall()` fallback branch, which
        # sqlite-only testing can never reach (sqlite3.Cursor.execute()
        # returns self, not a rowcount).
        cursor = make_mysql_cursor(fetchall=[{"id": 1, "name": "dog"}])
        result = self.resource.get(cursor)
        self.assertEqual(result, {"animals": [{"id": 1, "name": "dog"}]})

    def test_get_mysqlMocked_byKey_fallbackFetchonePath(self):
        cursor = make_mysql_cursor(fetchone={"id": 1, "name": "dog"})
        result = self.resource.get(cursor, key=1)
        self.assertEqual(result, {"id": 1, "name": "dog"})

    def test_post_mysqlMocked_lastrowidFallback(self):
        # executed.lastrowid raises AttributeError on an int (mysql-like
        # execute() return value); falls back to db.lastrowid.
        cursor = make_mysql_cursor(
            execute_returns=1, lastrowid=42, fetchone={"id": 42, "name": "new"}
        )
        result = self.resource.post(cursor, name="new")
        self.assertEqual(bottle.response.status_code, 201)
        self.assertEqual(result, {"id": 42, "name": "new"})

    def test_post_integrityError_mysqlMocked(self):
        cursor = make_mysql_cursor(
            execute_side_effect=pymysql.IntegrityError("Duplicate entry")
        )
        result = self.resource.post(cursor, name="dup")
        self.assertEqual(bottle.response.status_code, 422)
        self.assertEqual(result["message"], "Duplicate entry")

    def test_getRefs_mysqlMocked_bindCharPercentS_nesting(self):
        fk_rows = [
            {
                "table_name": "predations",
                "column_name": "predator",
                "referenced_table_name": "animals",
                "referenced_column_name": "id",
            },
            {
                "table_name": "predations",
                "column_name": "prey",
                "referenced_table_name": "animals",
                "referenced_column_name": "id",
            },
        ]
        cursor = make_mysql_cursor()
        cursor.execute.side_effect = None
        cursor.execute.return_value = 1
        cursor.fetchall.side_effect = [fk_rows]
        cursor.fetchone.return_value = {"id": 6, "name": "wolf"}

        PredationResource = resource_factory.createResource(
            "predations",
            [
                {"name": "id", "type": "INTEGER", "notnull": True, "default": None, "key": 1},
                {"name": "predator", "type": "INTEGER", "notnull": False, "default": None, "key": 0},
                {"name": "prey", "type": "INTEGER", "notnull": False, "default": None, "key": 0},
            ],
            sql=True,
        )
        instance = PredationResource()
        # prey=None exercises the `if not row[col]: continue` skip branch.
        row = {"id": 1, "predator": 6, "prey": None}
        instance.getRefs(cursor, "predations", row, levels=2)
        self.assertEqual(row["predator"]["name"], "wolf")
        self.assertIsNone(row["prey"])

    def test_nestedRefTableRefId_mysqlMocked_matchingFK_200(self):
        fk_rows = [
            {
                "table_name": "predations",
                "column_name": "predator",
                "referenced_table_name": "animals",
                "referenced_column_name": "id",
            }
        ]
        cursor = make_mysql_cursor()
        cursor.execute.side_effect = None
        cursor.execute.return_value = 1
        cursor.fetchall.side_effect = [fk_rows, [{"id": 1, "predator": 6}]]

        PredationResource = resource_factory.createResource(
            "predations",
            [
                {"name": "id", "type": "INTEGER", "notnull": True, "default": None, "key": 1},
                {"name": "predator", "type": "INTEGER", "notnull": False, "default": None, "key": 0},
            ],
            sql=True,
        )
        instance = PredationResource()
        result = instance.get(cursor, ref_table="animals", ref_id=6)
        self.assertEqual(result["predations"], [{"id": 1, "predator": 6}])

    def test_nestedRefTableRefId_mysqlMocked_noMatchingFK_404(self):
        cursor = make_mysql_cursor(fetchall=[])
        PredationResource = resource_factory.createResource(
            "predations",
            [
                {"name": "id", "type": "INTEGER", "notnull": True, "default": None, "key": 1},
                {"name": "predator", "type": "INTEGER", "notnull": False, "default": None, "key": 0},
            ],
            sql=True,
        )
        instance = PredationResource()
        result = instance.get(cursor, ref_table="nonexistent", ref_id=1)
        self.assertEqual(bottle.response.status_code, 404)
        self.assertEqual(result, {"message": "Resource not found"})

    def test_put_mysqlMocked_replacesFields(self):
        cursor = make_mysql_cursor(fetchone={"id": 1, "name": "new"})
        result = self.resource.put(cursor, key=1, name="new")
        self.assertEqual(bottle.response.status_code, 200)
        self.assertEqual(result, {"id": 1, "name": "new"})

    def test_put_mysqlMocked_exception_500(self):
        cursor = make_mysql_cursor(execute_side_effect=Exception("boom"))
        result = self.resource.put(cursor, key=1, name="new")
        self.assertEqual(bottle.response.status_code, 500)
        self.assertIn("message", result)

    def test_delete_mysqlMocked_success(self):
        cursor = make_mysql_cursor()
        result = self.resource.delete(cursor, 1)
        self.assertEqual(bottle.response.status_code, 200)
        self.assertIn("message", result)
        cursor.execute.assert_called_once()
        self.assertIn("%s", cursor.execute.call_args[0][0])

    def test_delete_mysqlMocked_exception_500(self):
        cursor = make_mysql_cursor(execute_side_effect=Exception("boom"))
        result = self.resource.delete(cursor, 1)
        self.assertEqual(bottle.response.status_code, 500)
        self.assertIn("message", result)


if __name__ == "__main__":
    unittest.main()
