import unittest
import webtest
from src.bottle_suite import BottleSuite
import bottle_rest
import bottle_jwt
import toml
import os
os.chdir("tests")

DEBUG = False

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
        self.bottle_suite = BottleSuite(gen_res=False)
        self.app = webtest.TestApp(self.bottle_suite)

    def addTestResource(self):
        self.bottle_suite.rest.addResource(TestResource, "/test_resource")

    def test_init(self):
        pass

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
        self.assertIsNone(next((p for p in self.bottle_suite.plugins if "API" in str(p)), None))

    def test_addResource(self):
        self.addTestResource()
        self.assertIn("TestResource", self.bottle_suite.resource_names)
        self.assertEqual(200, self.app.get('/test_resource').status_code)

    def test_restMethods(self):
        self.addTestResource()
        self.assertEqual(self.app.options("/test_resource").status_code, 200)
        self.assertEqual(self.app.get("/test_resource").status_code, 200)
        self.assertEqual(self.app.post("/test_resource").status_code, 200)
        self.assertEqual(self.app.put("/test_resource").status_code, 200)
        self.assertEqual(self.app.patch("/test_resource").status_code, 200)
        self.assertEqual(self.app.delete("/test_resource").status_code, 200)

    def test_genFileResource(self):
        self.bottle_suite = BottleSuite()
        self.app = webtest.TestApp(self.bottle_suite)
        self.assertIn("FileResource", self.bottle_suite.resource_names)
        self.assertEqual(200, self.app.get("/file_resource").status_code)

    # JWT
    def test_initJWT(self):
        self.assertIsInstance(self.bottle_suite.jwt, bottle_jwt.JWTPlugin)


    def test_initNoJWT(self):
        self.bottle_suite = BottleSuite(jwt=False, cfg_file=None)
        self.assertIsNone(next((p for p in self.bottle_suite.plugins if "JWT" in str(p)), None))


    # SQL
    def test_initSQLite(self):
        self.assertIsNotNone(self.bottle_suite.sqlite)

    def test_initNoSQLite(self):
        pass

    

    # CORS