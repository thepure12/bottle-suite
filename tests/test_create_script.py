import _paths  # noqa: F401
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

import toml

from scripts import create


class TestGetResourceName(unittest.TestCase):
    def test_uses_args_value(self):
        args = unittest.mock.Mock(resource=" Widget ")
        self.assertEqual(create.getResourceName(args), "widget")

    def test_prompts_when_missing(self):
        args = unittest.mock.Mock(resource=None)
        with patch("builtins.input", return_value=" Gadget "):
            self.assertEqual(create.getResourceName(args), "gadget")

    def test_keyboard_interrupt_exits(self):
        args = unittest.mock.Mock(resource=None)
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            with self.assertRaises(SystemExit):
                create.getResourceName(args)


class TestResourceFileAndConfig(unittest.TestCase):
    def setUp(self):
        self.orig_cwd = os.getcwd()
        self.tmpdir = tempfile.mkdtemp()
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.tmpdir)

    def test_createResourceFile_writes_scaffold(self):
        create.createResourceFile("my_widget")
        path = os.path.join(self.tmpdir, "resources", "my_widget.py")
        self.assertTrue(os.path.exists(path))
        with open(path) as f:
            content = f.read()
        self.assertIn("class MyWidget(Resource):", content)

    def test_createResourceFile_invalid_name_exits(self):
        with self.assertRaises(SystemExit):
            create.createResourceFile("123-bad")
        self.assertFalse(os.path.exists(os.path.join(self.tmpdir, "resources")))

    def test_createResourceFile_existing_file_exits(self):
        create.createResourceFile("widget")
        with self.assertRaises(SystemExit):
            create.createResourceFile("widget")

    def test_updateResourceConfig_creates_new_cfg(self):
        create.updateResourceConfig("widget")
        cfg_path = os.path.join(self.tmpdir, "bottle_suite.toml")
        self.assertTrue(os.path.exists(cfg_path))
        with open(cfg_path) as f:
            written = toml.load(f)
        self.assertEqual(
            written["resources"]["widget"]["paths"], ["/widget", "/widget/<key>"]
        )

    def test_updateResourceConfig_merges_existing_cfg(self):
        with open("bottle_suite.toml", "w") as f:
            toml.dump({"cors": True, "resources": {"other": {"paths": ["/other"]}}}, f)
        create.updateResourceConfig("widget")
        with open("bottle_suite.toml") as f:
            written = toml.load(f)
        self.assertTrue(written["cors"])
        self.assertEqual(written["resources"]["other"]["paths"], ["/other"])
        self.assertEqual(
            written["resources"]["widget"]["paths"], ["/widget", "/widget/<key>"]
        )

    def test_resource_end_to_end(self):
        with patch("sys.argv", ["bottle-suite-resource", "end_to_end"]):
            create.resource()
        self.assertTrue(os.path.exists("resources/end_to_end.py"))
        with open("bottle_suite.toml") as f:
            written = toml.load(f)
        self.assertEqual(
            written["resources"]["end_to_end"]["paths"],
            ["/end_to_end", "/end_to_end/<key>"],
        )


class TestSetupDashboardAuth(unittest.TestCase):
    def setUp(self):
        self.orig_cwd = os.getcwd()
        self.tmpdir = tempfile.mkdtemp()
        os.chdir(self.tmpdir)
        self.cfg_patcher = patch.object(create, "cfg", {"cors": True})
        self.cfg_patcher.start()

    def tearDown(self):
        self.cfg_patcher.stop()
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.tmpdir)

    def test_declines_writes_nothing(self):
        with patch("builtins.input", return_value="n"):
            create.setupDashboardAuth(self.tmpdir)
        self.assertFalse(os.path.exists(os.path.join(self.tmpdir, "bottle_suite.toml")))
        self.assertNotIn("dashboard", create.cfg)

    def test_empty_password_skips(self):
        with patch("builtins.input", side_effect=["y", "admin", ""]):
            create.setupDashboardAuth(self.tmpdir)
        self.assertNotIn("dashboard", create.cfg)
        self.assertFalse(os.path.exists(os.path.join(self.tmpdir, "bottle_suite.toml")))

    def test_sets_up_credentials(self):
        with patch("builtins.input", side_effect=["y", "myadmin", "hunter2"]):
            create.setupDashboardAuth(self.tmpdir)
        self.assertEqual(create.cfg["dashboard"]["username"], "myadmin")
        self.assertTrue(create.cfg["dashboard"]["password_hash"])
        with open(os.path.join(self.tmpdir, "bottle_suite.toml")) as f:
            written = toml.load(f)
        self.assertEqual(written["dashboard"]["username"], "myadmin")

    def test_default_username(self):
        with patch("builtins.input", side_effect=["y", "", "hunter2"]):
            create.setupDashboardAuth(self.tmpdir)
        self.assertEqual(create.cfg["dashboard"]["username"], "admin")


if __name__ == "__main__":
    unittest.main()
