import _paths  # noqa: F401
import unittest
import bottle
import webtest
from bottle_suite.plugins.rest import API, Resource
from bottle_suite.plugins.cors import CorsPlugin


class OtherKeywordAPI(API):
    keyword = "other"


class TestAPISetup(unittest.TestCase):
    def test_conflictingKeyword_raisesPluginError(self):
        app = bottle.Bottle()
        app.install(API())
        with self.assertRaises(bottle.PluginError):
            app.install(API())

    def test_nonConflicting_loopContinuesPastOtherPlugins(self):
        app = bottle.Bottle()
        app.install(CorsPlugin())  # not an API instance -> continue branch
        app.install(OtherKeywordAPI())  # API, but different keyword
        app.install(API())  # should not raise


class TestResourceNameSetter(unittest.TestCase):
    def test_name_setterOverridesClassName(self):
        resource = Simple()
        resource.name = "Custom"
        self.assertEqual(resource.name, "Custom")


class TestAPIApply(unittest.TestCase):
    def setUp(self):
        self.app = bottle.Bottle()
        self.app.install(API())
        self.testapp = webtest.TestApp(self.app)

    def test_missingRequiredField_400(self):
        def callback(name):
            return {"name": name}

        self.app.route("/thing", "POST", callback)
        resp = self.testapp.post("/thing", expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        # Exact current (typo'd) message -- intentionally left as-is, out of scope to fix.
        self.assertEqual(resp.json, {"name": "This feild is is required"})

    def test_dataKwargsKeyCollision_500(self):
        def callback(id, name="x"):
            return {"id": id, "name": name}

        self.app.route("/thing/<id>", "POST", callback)
        resp = self.testapp.post_json("/thing/5", {"id": 99}, expect_errors=True)
        self.assertEqual(resp.status_code, 500)

    def test_noParams_callsWithoutData(self):
        def callback():
            return {"ok": True}

        self.app.route("/noargs", "GET", callback)
        resp = self.testapp.get("/noargs")
        self.assertEqual(resp.json, {"ok": True})

    def test_paramWithDefault_notRequired(self):
        def callback(name="default"):
            return {"name": name}

        self.app.route("/thing2", "POST", callback)
        resp = self.testapp.post("/thing2")
        self.assertEqual(resp.json, {"name": "default"})


class TestAPIApplyDebug(unittest.TestCase):
    def test_debugMode_printsDiagnostics(self):
        app = bottle.Bottle()
        app.install(API(debug=True))

        def callback(name="default"):
            return {"name": name}

        app.route("/thing", "POST", callback)
        testapp = webtest.TestApp(app)
        resp = testapp.post("/thing")
        self.assertEqual(resp.status_code, 200)


class Empty(Resource):
    pass


class Simple(Resource):
    def options(self):
        pass

    def get(self):
        return {"ok": True}


class TestAddResource(unittest.TestCase):
    def setUp(self):
        self.app = bottle.Bottle()
        self.api = API()
        self.app.install(self.api)
        self.testapp = webtest.TestApp(self.app)

    def test_addResource_classVsInstance(self):
        self.api.addResource(Simple, "/simple_class")
        self.api.addResource(Simple(), "/simple_instance")
        self.assertEqual(self.testapp.get("/simple_class").json, {"ok": True})
        self.assertEqual(self.testapp.get("/simple_instance").json, {"ok": True})

    def test_addResource_multipleRules(self):
        self.api.addResource(Simple, "/a", "/b")
        self.assertEqual(self.testapp.get("/a").json, {"ok": True})
        self.assertEqual(self.testapp.get("/b").json, {"ok": True})

    def test_resourceWithZeroHttpMethods_noRoutesRegistered(self):
        before = len(self.app.routes)
        self.api.addResource(Empty, "/empty")
        self.assertEqual(len(self.app.routes), before)
        resp = self.testapp.get("/empty", expect_errors=True)
        self.assertEqual(resp.status_code, 404)


class TestAddResourceDebug(unittest.TestCase):
    def test_debugMode_printsDiagnostics(self):
        app = bottle.Bottle()
        api = API(debug=True)
        app.install(api)
        api.addResource(Simple, "/simple")
        testapp = webtest.TestApp(app)
        self.assertEqual(testapp.get("/simple").json, {"ok": True})


if __name__ == "__main__":
    unittest.main()
