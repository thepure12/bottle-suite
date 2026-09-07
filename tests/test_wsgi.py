import _paths  # noqa: F401
import unittest
import importlib
import os

import bottle_suite.wsgi as wsgi_module
from bottle_suite import BottleSuite

NONEXISTENT_CFG = "no_such_bottle_suite_cfg.toml"


class TestWsgi(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("BOTTLE_SUITE_CFG", None)
        importlib.reload(wsgi_module)

    def test_default_cfg_file_from_cwd(self):
        importlib.reload(wsgi_module)
        self.assertIsInstance(wsgi_module.application, BottleSuite)
        self.assertEqual(wsgi_module.application.cfg_file, "bottle_suite.toml")

    def test_cfg_file_overridden_by_env(self):
        os.environ["BOTTLE_SUITE_CFG"] = NONEXISTENT_CFG
        importlib.reload(wsgi_module)
        self.assertEqual(wsgi_module.application.cfg_file, NONEXISTENT_CFG)
        self.assertEqual(wsgi_module.application.cfg, {})
