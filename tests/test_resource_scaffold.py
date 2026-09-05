import _paths  # noqa: F401
import unittest
from bottle_suite import resource_scaffold


class TestResourceScaffold(unittest.TestCase):
    def test_render_returnsClassWithGivenName(self):
        result = resource_scaffold.render("Foo")
        self.assertEqual(result, resource_scaffold.TEMPLATE.format(class_name="Foo"))
        self.assertIn("class Foo(Resource):", result)

    def test_nameRe_matchesValidLowerSnakeCase(self):
        self.assertTrue(resource_scaffold.NAME_RE.match("my_resource"))
        self.assertTrue(resource_scaffold.NAME_RE.match("resource"))
        self.assertTrue(resource_scaffold.NAME_RE.match("_leading_underscore"))

    def test_nameRe_rejectsInvalidNames(self):
        self.assertIsNone(resource_scaffold.NAME_RE.match("MyResource"))
        self.assertIsNone(resource_scaffold.NAME_RE.match("123abc"))
        self.assertIsNone(resource_scaffold.NAME_RE.match("my-resource"))


if __name__ == "__main__":
    unittest.main()
