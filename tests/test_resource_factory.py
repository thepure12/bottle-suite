from src.bottle_suite import resource_factory
import unittest

class TestResourceFactory(unittest.TestCase):

    def setUp(self) -> None:
        pass

    def test_creatSQLResource(self):
        pass

    def test_createSQLiteResource(self):
        fields = []
        resource = resource_factory.createResource("TestResource", fields, sql=True)
        pass