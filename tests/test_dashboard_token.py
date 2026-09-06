import _paths  # noqa: F401
import unittest
import os
import tempfile
import webtest
from bottle_suite import BottleSuite
from bottle_suite.dashboard.resources.token import DashboardToken, hashPassword

NONEXISTENT_CFG = "no_such_bottle_suite_cfg.toml"


class FakeApp:
    """Minimal stand-in for BottleSuite -- DashboardToken only ever touches
    .cfg/.saveConfig()/.reloadServer(), so a full app isn't needed for the
    pure authenticate()/isConfigured() logic."""

    def __init__(self, cfg=None):
        self.cfg = cfg if cfg is not None else {}
        self.save_calls = 0
        self.reload_calls = 0

    def saveConfig(self):
        self.save_calls += 1

    def reloadServer(self):
        self.reload_calls += 1


class TestDashboardTokenAuthenticate(unittest.TestCase):
    def test_authenticate_notConfigured_returnsNone(self):
        token = DashboardToken(FakeApp())
        self.assertIsNone(token.authenticate(username="anyone", password="anything"))
        self.assertIsNone(token.authenticate())

    def test_authenticate_dashboardCfgNotADict_returnsNone(self):
        # e.g. `dashboard = true` (the plain enable/disable form) with no
        # credentials table configured yet.
        token = DashboardToken(FakeApp(cfg={"dashboard": True}))
        self.assertIsNone(token.authenticate(username="anyone", password="anything"))

    def test_authenticate_correctCredentials_succeeds(self):
        app = FakeApp(
            cfg={"dashboard": {"username": "admin", "password_hash": hashPassword("secret")}}
        )
        token = DashboardToken(app)
        self.assertEqual(
            token.authenticate(username="admin", password="secret"), {"user": "admin"}
        )

    def test_authenticate_dashboardDictMissingHash_returnsNone(self):
        # A dict is present (e.g. only `enabled` was ever set) but no
        # credentials have actually been configured yet.
        token = DashboardToken(FakeApp(cfg={"dashboard": {"enabled": True}}))
        self.assertIsNone(token.authenticate(username="anyone", password="anything"))

    def test_authenticate_wrongPassword_returnsNone(self):
        app = FakeApp(
            cfg={"dashboard": {"username": "admin", "password_hash": hashPassword("secret")}}
        )
        token = DashboardToken(app)
        self.assertIsNone(token.authenticate(username="admin", password="wrong"))

    def test_authenticate_wrongUsername_returnsNone(self):
        app = FakeApp(
            cfg={"dashboard": {"username": "admin", "password_hash": hashPassword("secret")}}
        )
        token = DashboardToken(app)
        self.assertIsNone(token.authenticate(username="notadmin", password="secret"))

    def test_isConfigured_reflectsCfgState(self):
        token = DashboardToken(FakeApp())
        self.assertFalse(token.isConfigured())
        token.app.cfg["dashboard"] = {"username": "admin", "password_hash": "x"}
        self.assertTrue(token.isConfigured())

    def test_get_reportsConfiguredStatus(self):
        token = DashboardToken(FakeApp())
        self.assertEqual(token.get(), {"configured": False})
        token.app.cfg["dashboard"] = {"username": "admin", "password_hash": "x"}
        self.assertEqual(token.get(), {"configured": True})

    def test_post_setsCredentials_whenNotConfigured(self):
        app = FakeApp()
        token = DashboardToken(app)
        result = token.post("admin", "secret")
        self.assertEqual(result, {"configured": True})
        self.assertTrue(token.isConfigured())
        self.assertEqual(app.save_calls, 1)
        self.assertEqual(app.reload_calls, 1)
        self.assertEqual(
            token.authenticate(username="admin", password="secret"), {"user": "admin"}
        )

    def test_post_preservesExistingDictKeys(self):
        app = FakeApp(cfg={"dashboard": {"enabled": False}})
        token = DashboardToken(app)
        token.post("admin", "secret")
        self.assertFalse(app.cfg["dashboard"]["enabled"])
        self.assertEqual(app.cfg["dashboard"]["username"], "admin")

    def test_post_rejectsWhenAlreadyConfigured(self):
        app = FakeApp(
            cfg={"dashboard": {"username": "admin", "password_hash": hashPassword("secret")}}
        )
        token = DashboardToken(app)
        result = token.post("someone", "else")
        self.assertEqual(
            result, {"message": "Dashboard admin credentials are already configured"}
        )
        # Original credentials must be untouched.
        self.assertEqual(app.cfg["dashboard"]["username"], "admin")
        self.assertEqual(app.save_calls, 0)

    def test_post_missingUsernameOrPassword_rejected(self):
        app = FakeApp()
        token = DashboardToken(app)
        self.assertEqual(
            token.post("", "secret"), {"message": "username and password are required"}
        )
        self.assertEqual(
            token.post("admin", ""), {"message": "username and password are required"}
        )
        self.assertFalse(token.isConfigured())

    def test_options_isNoop(self):
        token = DashboardToken(FakeApp())
        self.assertIsNone(token.options())


class TestDashboardSetupEndpoint(unittest.TestCase):
    """End-to-end coverage of the /dashboard/setup resource wired up by
    BottleSuite.setupDashboard/setupRest, including the JWT-plugin route
    bypass (no roles configured -> reachable with no token)."""

    def _writeCfg(self, content):
        fd, path = tempfile.mkstemp(suffix=".toml", dir=os.getcwd())
        os.close(fd)
        with open(path, "w") as f:
            f.write(content)
        self.addCleanup(os.remove, path)
        return path

    def _app(self):
        path = self._writeCfg("")
        bs = BottleSuite(
            cfg_file=path, dashboard=True, jwt="k", sqlite=False, sql=False,
            gen_res=False, gen_db=False,
        )
        return bs, webtest.TestApp(bs)

    def test_setupDashboard_wiresBoundAuthenticate(self):
        bs, _ = self._app()
        self.assertEqual(
            bs.jwt.token_paths["dashboardtoken"], bs.dashboard_token.authenticate
        )

    def test_get_reportsNotConfigured_thenConfigured(self):
        bs, app = self._app()
        resp = app.get("/dashboard/setup")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {"configured": False})

        app.post_json("/dashboard/setup", {"username": "admin", "password": "secret"})

        resp = app.get("/dashboard/setup")
        self.assertEqual(resp.json, {"configured": True})

    def test_post_thenLogin_succeeds(self):
        bs, app = self._app()
        resp = app.post_json(
            "/dashboard/setup", {"username": "admin", "password": "secret"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {"configured": True})

        resp = app.post_json(
            "/dashboard/token", {"username": "admin", "password": "secret"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("token", resp.json)

    def test_post_secondAttempt_rejected403(self):
        bs, app = self._app()
        app.post_json("/dashboard/setup", {"username": "admin", "password": "secret"})

        resp = app.post_json(
            "/dashboard/setup",
            {"username": "someone", "password": "else"},
            expect_errors=True,
        )
        self.assertEqual(resp.status_code, 403)

    def test_post_missingFields_400(self):
        bs, app = self._app()
        resp = app.post_json("/dashboard/setup", {}, expect_errors=True)
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
