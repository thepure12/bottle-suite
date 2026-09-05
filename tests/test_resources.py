import _paths  # noqa: F401
import unittest
import os
import shutil
import tempfile
import toml
import webtest
from bottle_suite import BottleSuite
from bottle_suite.resources import Config, DataTypes, AllResources, PythonResources
from bottle_suite.plugins import rest as bottle_rest
import db_fixtures

NONEXISTENT_CFG = "no_such_bottle_suite_cfg.toml"


class CustomResource(bottle_rest.Resource):
    """A hand-registered, non-DB-table resource -- used to prove
    AllResources.get() (list mode) excludes resources with no .table
    attribute."""

    def options(self):
        pass

    def get(self):
        return {}


class TestConfigResource(unittest.TestCase):
    def setUp(self):
        # bottle_suite.toml's own values (e.g. sqlite="resources.db") always
        # win over constructor args once loaded, so a copied cfg_file is
        # sufficient isolation here -- Config's get/put never touch DB rows.
        self.cfg_dir, self.cfg_path = db_fixtures.temp_cfg_copy()
        self.bs = BottleSuite(
            cfg_file=self.cfg_path,
            jwt=False,
            gen_res=False,
            gen_db=False,
        )
        self.app = webtest.TestApp(self.bs)

    def tearDown(self):
        shutil.rmtree(self.cfg_dir)

    def test_get_dumpsToml(self):
        resp = self.app.get("/bottle_suite_cfg")
        self.assertEqual(resp.status_code, 200)
        dumped = toml.loads(resp.text)
        self.assertEqual(dumped, self.bs.cfg)

    def test_put_validToml_replacesConfig(self):
        resp = self.app.put_json("/bottle_suite_cfg", {"config": "cors = false\n"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.bs.cfg, {"cors": False})
        on_disk = toml.load(self.cfg_path)
        self.assertEqual(on_disk, {"cors": False})

    def test_options_isNoop(self):
        # CORS intercepts OPTIONS before it reaches the handler over HTTP,
        # so this is exercised as a direct unit call.
        self.assertIsNone(Config(self.bs).options())

    def test_put_malformedToml_400(self):
        resp = self.app.put_json(
            "/bottle_suite_cfg", {"config": "not: valid: toml: ["}, expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("message", resp.json)


class TestDataTypesResource(unittest.TestCase):
    def test_get_sqliteConfigured_returnsList(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        try:
            bs = BottleSuite(
                cfg_file=NONEXISTENT_CFG,
                jwt=False,
                sqlite=tmp_db,
                gen_res=False,
                gen_db=False,
            )
            app = webtest.TestApp(bs)
            resp = app.get("/_datatypes")
            self.assertEqual(resp.status_code, 200)
            self.assertIn("TEXT", resp.json["datatypes"])
        finally:
            os.remove(tmp_db)

    def test_options_isNoop(self):
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        self.assertIsNone(DataTypes(bs).options())

    def test_get_noSqlite_returnsEmptyBody(self):
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG,
            jwt=False,
            sqlite=False,
            sql=False,
            gen_res=False,
            gen_db=False,
        )
        app = webtest.TestApp(bs)
        resp = app.get("/_datatypes")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.body, b"")


class TestAllResourcesGet(unittest.TestCase):
    def setUp(self):
        self.tmp_db = db_fixtures.temp_sqlite_copy()
        self.bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG,
            jwt=False,
            sqlite=self.tmp_db,
            gen_res=False,
            gen_db=True,
        )
        self.app = webtest.TestApp(self.bs)

    def tearDown(self):
        os.remove(self.tmp_db)

    def test_list_includesDbResources(self):
        resp = self.app.get("/_resources")
        names = [r["name"] for r in resp.json["resources"]]
        self.assertIn("Animals", names)
        self.assertIn("Predations", names)

    def test_list_excludesNonDbResources_characterized(self):
        self.bs.rest.addResource(CustomResource, "/custom")
        resp = self.app.get("/_resources")
        names = [r["name"] for r in resp.json["resources"]]
        self.assertNotIn("CustomResource", names)

    def test_single_found(self):
        resp = self.app.get("/_resources/animals")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json["name"], "animals")
        self.assertIn("fields", resp.json)
        self.assertIn("roles", resp.json)
        self.assertIn("paths", resp.json)

    def test_single_found_partialRolesConfigured_skipsExisting(self):
        path = self._writeCfg('[resources.animals.roles]\nget = true\n')
        bs = BottleSuite(
            cfg_file=path, jwt=False, sqlite=self.tmp_db, gen_res=False,
            gen_db=True,
        )
        app = webtest.TestApp(bs)
        resp = app.get("/_resources/animals")
        roles = {r["method"]: r["roles"] for r in resp.json["roles"]}
        self.assertEqual(roles["get"], True)
        self.assertEqual(roles["post"], False)

    def _writeCfg(self, content):
        import tempfile

        fd, path = tempfile.mkstemp(suffix=".toml", dir=os.getcwd())
        os.close(fd)
        with open(path, "w") as f:
            f.write(content)
        self.addCleanup(os.remove, path)
        return path

    def test_single_caseInsensitiveMatch(self):
        resp = self.app.get("/_resources/ANIMALS")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json["name"], "animals")

    def test_single_notFound_404_helpfulMessage(self):
        resp = self.app.get("/_resources/nope", expect_errors=True)
        self.assertEqual(resp.status_code, 404)
        self.assertIn("animals", resp.json["message"])

    def test_options_isNoop(self):
        all_resources = next(r for r in self.bs.rest.resources if r.name == "AllResources")
        self.assertIsNone(all_resources.options())

    def test_list_duplicateNameBothWithTable_lastTableWins_characterized(self):
        # Two resources sharing a .name, both with a .table attribute --
        # documents that the TODO'd branch ("handle resource with multiple
        # tables") just overwrites with the later one.
        class Fake:
            name = "Dup"
            table = "table_a"

        class Fake2:
            name = "Dup"
            table = "table_b"

        self.bs.rest.resources.append(Fake())
        self.bs.rest.resources.append(Fake2())
        resp = self.app.get("/_resources")
        dup_entries = [r for r in resp.json["resources"] if r["name"] == "Dup"]
        self.assertEqual(dup_entries, [{"name": "Dup", "id": "table_b"}])

    def test_list_duplicateNameSecondHasNoTable_firstTableKept(self):
        class Fake:
            name = "Dup2"
            table = "table_a"

        class Fake2:
            name = "Dup2"
            # no .table attribute -> getattr(..., "table", None) is falsy

        self.bs.rest.resources.append(Fake())
        self.bs.rest.resources.append(Fake2())
        resp = self.app.get("/_resources")
        dup_entries = [r for r in resp.json["resources"] if r["name"] == "Dup2"]
        self.assertEqual(dup_entries, [{"name": "Dup2", "id": "table_a"}])


class TestAllResourcesPost(unittest.TestCase):
    def test_post_sqlite_createsTable(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        try:
            bs = BottleSuite(
                cfg_file=NONEXISTENT_CFG,
                jwt=False,
                sqlite=tmp_db,
                gen_res=False,
                gen_db=False,
            )
            app = webtest.TestApp(bs)
            resp = app.post_json("/_resources", {"name": "newthing"})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json["id"], "newthing")
            self.assertIn("newthing", bs.getDBTables())
        finally:
            os.remove(tmp_db)

    def test_post_mysqlConfigured_noopCharacterized(self):
        bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG,
            jwt=False,
            sqlite=False,
            sql={"host": "fake", "user": "u", "password": "p", "database": "d"},
            gen_res=False,
            gen_db=False,
        )
        all_resources = next(r for r in bs.rest.resources if r.name == "AllResources")
        result = all_resources.post("newthing")
        self.assertEqual(result["id"], "newthing")

    def test_post_invalidName_400(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        try:
            bs = BottleSuite(
                cfg_file=NONEXISTENT_CFG,
                jwt=False,
                sqlite=tmp_db,
                gen_res=False,
                gen_db=False,
            )
            app = webtest.TestApp(bs)
            resp = app.post_json(
                "/_resources", {"name": "bad name"}, expect_errors=True
            )
            self.assertEqual(resp.status_code, 400)
            self.assertIn("message", resp.json)
        finally:
            os.remove(tmp_db)

    def test_post_duplicateName_400(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        try:
            bs = BottleSuite(
                cfg_file=NONEXISTENT_CFG,
                jwt=False,
                sqlite=tmp_db,
                gen_res=False,
                gen_db=False,
            )
            app = webtest.TestApp(bs)
            app.post_json("/_resources", {"name": "newthing"})
            resp = app.post_json(
                "/_resources", {"name": "newthing"}, expect_errors=True
            )
            self.assertEqual(resp.status_code, 400)
            self.assertIn("message", resp.json)
        finally:
            os.remove(tmp_db)


class TestAllResourcesPatch(unittest.TestCase):
    def setUp(self):
        self.tmp_db = db_fixtures.temp_sqlite_copy()
        self.cfg_dir, self.cfg_path = db_fixtures.temp_cfg_pointing_at(self.tmp_db)
        self.bs = BottleSuite(
            cfg_file=self.cfg_path,
            jwt=False,
            sqlite=self.tmp_db,
            gen_res=False,
            gen_db=True,
        )
        self.app = webtest.TestApp(self.bs)

    def tearDown(self):
        os.remove(self.tmp_db)
        shutil.rmtree(self.cfg_dir)

    def test_patch_roles_dispatch(self):
        resp = self.app.patch_json(
            "/_resources/animals",
            {"attr_name": "roles", "value": {"method": "get", "roles": "admin,user"}},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            self.bs.cfg["resources"]["animals"]["roles"]["get"], ["admin", "user"]
        )

    def test_patch_roles_listInput_noCrash(self):
        # Regression for fix #6.
        resp = self.app.patch_json(
            "/_resources/animals",
            {"attr_name": "roles", "value": {"method": "get", "roles": ["admin"]}},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            self.bs.cfg["resources"]["animals"]["roles"]["get"], ["admin"]
        )

    def test_patch_paths_dispatch(self):
        resp = self.app.patch_json(
            "/_resources/animals",
            {"attr_name": "paths", "value": {"index": 0, "path": "/critters"}},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            self.bs.cfg["resources"]["animals"]["paths"][0], "/critters"
        )

    def test_patch_fields_dispatch(self):
        resp = self.app.patch_json(
            "/_resources/animals",
            {
                "attr_name": "fields",
                "value": {
                    "cid": 1,
                    "name": "critter_name",
                    "type": "TEXT",
                    "notnull": 0,
                    "dflt_value": None,
                    "pk": 0,
                },
            },
        )
        self.assertEqual(resp.status_code, 200)
        fields = self.bs.getDBTable(self.bs.getDBCursor(), "animals")
        self.assertIn("critter_name", [f["name"] for f in fields])

    def test_patch_unrecognizedAttrName_noop_characterized(self):
        resp = self.app.patch_json(
            "/_resources/animals", {"attr_name": "bogus", "value": {}}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.body, b"")

    def test_patch_malformedBody_missingMethodKey_400(self):
        # Regression for fix #12.
        resp = self.app.patch_json(
            "/_resources/animals",
            {"attr_name": "roles", "value": {"roles": "admin"}},
            expect_errors=True,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("message", resp.json)

    def test_patch_malformedBody_missingIndexKey_400(self):
        resp = self.app.patch_json(
            "/_resources/animals",
            {"attr_name": "paths", "value": {"path": "/x"}},
            expect_errors=True,
        )
        self.assertEqual(resp.status_code, 400)


class TestPythonResources(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.mkdtemp()
        os.chdir(self.tmp)
        self.bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG, jwt=False, sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        self.app = webtest.TestApp(self.bs)

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp)

    def test_options_isNoop(self):
        self.assertIsNone(PythonResources(self.bs).options())

    def test_get_noResourcesDir_returnsEmptyList(self):
        resp = self.app.get("/_python_resources")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json["resources"], [])

    def test_post_thenGet_listsCreatedResource(self):
        resp = self.app.post_json("/_python_resources", {"name": "widget"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {"name": "widget"})

        resp = self.app.get("/_python_resources")
        self.assertEqual(resp.json["resources"], [{"name": "widget"}])

    def test_post_invalidName_400(self):
        resp = self.app.post_json(
            "/_python_resources", {"name": "123bad"}, expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("message", resp.json)

    def test_post_duplicateName_400(self):
        self.app.post_json("/_python_resources", {"name": "widget"})
        resp = self.app.post_json(
            "/_python_resources", {"name": "widget"}, expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("message", resp.json)

    def test_single_found(self):
        self.app.post_json("/_python_resources", {"name": "widget"})
        resp = self.app.get("/_python_resources/widget")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json["name"], "widget")
        self.assertEqual(
            resp.json["paths"],
            [{"path": "/widget", "index": 0}, {"path": "/widget/<key>", "index": 1}],
        )
        roles = {r["method"]: r["roles"] for r in resp.json["roles"]}
        self.assertEqual(
            roles, {"get": False, "post": False, "put": False, "patch": False, "delete": False}
        )

    def test_single_notFound_404_helpfulMessage(self):
        resp = self.app.get("/_python_resources/nope", expect_errors=True)
        self.assertEqual(resp.status_code, 404)
        self.assertIn("message", resp.json)

    def test_patch_roles_dispatch(self):
        self.app.post_json("/_python_resources", {"name": "widget"})
        resp = self.app.patch_json(
            "/_python_resources/widget",
            {"attr_name": "roles", "value": {"method": "get", "roles": "admin,user"}},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            self.bs.cfg["resources"]["widget"]["roles"]["get"], ["admin", "user"]
        )

    def test_patch_paths_dispatch(self):
        self.app.post_json("/_python_resources", {"name": "widget"})
        resp = self.app.patch_json(
            "/_python_resources/widget",
            {"attr_name": "paths", "value": {"index": 0, "path": "/gadget"}},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            self.bs.cfg["resources"]["widget"]["paths"][0], "/gadget"
        )

    def test_patch_malformedBody_missingMethodKey_400(self):
        self.app.post_json("/_python_resources", {"name": "widget"})
        resp = self.app.patch_json(
            "/_python_resources/widget",
            {"attr_name": "roles", "value": {"roles": "admin"}},
            expect_errors=True,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("message", resp.json)

    def test_patch_unrecognizedAttrName_noop_characterized(self):
        self.app.post_json("/_python_resources", {"name": "widget"})
        resp = self.app.patch_json(
            "/_python_resources/widget", {"attr_name": "bogus", "value": {}}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.body, b"")


if __name__ == "__main__":
    unittest.main()
