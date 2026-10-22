import _paths  # noqa: F401
import unittest
import importlib
import os

import bottler.wsgi as wsgi_module
from bottler import Bottler

NONEXISTENT_CFG = "no_such_bottler_cfg.toml"


class TestWsgi(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("BOTTLER_CFG", None)
        importlib.reload(wsgi_module)

    def test_default_cfg_file_from_cwd(self):
        importlib.reload(wsgi_module)
        self.assertIsInstance(wsgi_module.application, Bottler)
        self.assertEqual(wsgi_module.application.cfg_file, "bottler.toml")

    def test_cfg_file_overridden_by_env(self):
        os.environ["BOTTLER_CFG"] = NONEXISTENT_CFG
        importlib.reload(wsgi_module)
        self.assertEqual(wsgi_module.application.cfg_file, NONEXISTENT_CFG)
        self.assertEqual(wsgi_module.application.cfg, {})
