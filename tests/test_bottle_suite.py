import unittest
import webtest
from src.bottle_suite import BottleSuite
import bottle_rest

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
        self.bottle_suite = BottleSuite()
        self.app = webtest.TestApp(self.bottle_suite)
        

    def addTestResource(self):
        self.bottle_suite.rest.addResource(TestResource, "/resource")

    def test_init(self):
        pass

    # REST
    def test_initRest(self):
        self.assertIn("AllResources", self.bottle_suite.resource_names)
        self.assertIn("DataTypes", self.bottle_suite.resource_names)

    def test_initNoRest(self):
        self.addTestResource()
        self.bottle_suite = BottleSuite(rest=False)
        self.assertIsNone(next((p for p in self.bottle_suite.plugins if "API" in str(p)), None))

    def test_addResource(self):
        self.addTestResource()
        self.assertIn("TestResource", self.bottle_suite.resource_names)

    def test_restMethods(self):
        self.addTestResource()
        self.assertEqual(self.app.options("/resource").status_code, 200)
        self.assertEqual(self.app.get("/resource").status_code, 200)
        self.assertEqual(self.app.post("/resource").status_code, 200)
        self.assertEqual(self.app.put("/resource").status_code, 200)
        self.assertEqual(self.app.patch("/resource").status_code, 200)
        self.assertEqual(self.app.delete("/resource").status_code, 200)

    

    # JWT

    # SQL

    # CORS