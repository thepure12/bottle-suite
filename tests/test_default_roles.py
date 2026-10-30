import _paths  # noqa: F401
import os
import tempfile
import unittest
from datetime import datetime, timedelta

import jwt as pyjwt
import webtest

import db_fixtures
from bottler import Bottler
from bottler.plugins import rest as bottle_rest
from bottler.resources import _buildRoles
from bottler.dashboard.resources.token import ADMIN_ROLE

JWT_KEY = "secret"


def _token(**payload_extra):
    payload = {"exp": datetime.utcnow() + timedelta(days=1), **payload_extra}
    return pyjwt.encode(payload, JWT_KEY, algorithm="HS256")


def _auth(**payload_extra):
    return {"Authorization": f"Bearer {_token(**payload_extra)}"}


def _makeResource():
    # A fresh class per test -- route config lives in class attributes, so a
    # shared class would carry one test's roles into the next.
    class Widget(bottle_rest.Resource):
        def options(self):
            pass

        def get(self):
            return {"ok": True}

        def post(self):
            return {"ok": True}

    return Widget


class TestDefaultRoles(unittest.TestCase):
    def _writeCfg(self, content):
        fd, path = tempfile.mkstemp(suffix=".toml", dir=os.getcwd())
        os.close(fd)
        with open(path, "w") as f:
            f.write(f'jwt = "{JWT_KEY}"\n' + content)
        self.addCleanup(os.remove, path)
        return path

    def _app(self, cfg="", resource=None, **kwargs):
        bs = Bottler(
            cfg_file=self._writeCfg(cfg), sqlite=False, sql=False,
            gen_res=False, gen_db=False, **kwargs,
        )
        resource = resource or _makeResource()
        bs.setRoles(resource, "widgets")
        bs.rest.addResource(resource, "/widgets")
        return bs, webtest.TestApp(bs)

    def test_unset_leavesRoutesOpen(self):
        _, app = self._app()
        self.assertEqual(app.get("/widgets").status_code, 200)

    def test_true_requiresAnyValidToken(self):
        _, app = self._app("default_roles = true\n")
        self.assertEqual(app.get("/widgets", expect_errors=True).status_code, 400)
        self.assertEqual(app.post("/widgets", expect_errors=True).status_code, 400)
        self.assertEqual(app.get("/widgets", headers=_auth()).status_code, 200)

    def test_kwarg_usedWhenCfgUnset(self):
        _, app = self._app(default_roles=True)
        self.assertEqual(app.get("/widgets", expect_errors=True).status_code, 400)

    def test_cfgOverridesKwarg(self):
        _, app = self._app("default_roles = false\n", default_roles=True)
        self.assertEqual(app.get("/widgets").status_code, 200)

    def test_list_requiresOneOfTheRoles(self):
        _, app = self._app('default_roles = ["admin", "finance"]\n')
        self.assertEqual(
            app.get("/widgets", headers=_auth(roles=["viewer"]), expect_errors=True).status_code,
            403,
        )
        self.assertEqual(app.get("/widgets", headers=_auth(roles=["finance"])).status_code, 200)

    def test_commaString_normalizedToList(self):
        bs, _ = self._app('default_roles = "admin,finance"\n')
        self.assertEqual(bs.default_roles, ["admin", "finance"])

    def test_perResourceRolesOverrideDefault(self):
        _, app = self._app(
            'default_roles = true\n[resources.widgets.roles]\nget = ["admin"]\n'
        )
        self.assertEqual(
            app.get("/widgets", headers=_auth(roles=["viewer"]), expect_errors=True).status_code,
            403,
        )
        # POST has no per-resource entry, so it falls back to the default.
        self.assertEqual(app.post("/widgets", headers=_auth(roles=["viewer"])).status_code, 200)

    def test_explicitFalseOptsOut(self):
        _, app = self._app("default_roles = true\n[resources.widgets.roles]\nget = false\n")
        self.assertEqual(app.get("/widgets").status_code, 200)
        self.assertEqual(app.post("/widgets", expect_errors=True).status_code, 400)

    def test_classDeclaredRolesWin(self):
        resource = _makeResource()
        resource.GET = {"roles": False}
        _, app = self._app("default_roles = true\n", resource=resource)
        self.assertEqual(app.get("/widgets").status_code, 200)

    def test_emptyList_turnsMethodOff(self):
        _, app = self._app("default_roles = true\n[resources.widgets.roles]\npost = []\n")
        self.assertEqual(app.get("/widgets", headers=_auth()).status_code, 200)
        self.assertEqual(
            app.post("/widgets", headers=_auth(roles=["admin"]), expect_errors=True).status_code,
            405,
        )

    def test_emptyList_allMethodsOff_noRoute(self):
        _, app = self._app("[resources.widgets.roles]\nget = []\npost = []\n")
        self.assertEqual(app.get("/widgets", expect_errors=True).status_code, 404)
        self.assertEqual(app.options("/widgets", expect_errors=True).status_code, 404)

    def test_emptyList_winsOverClassRoles(self):
        resource = _makeResource()
        resource.POST = {"roles": ["admin"]}
        _, app = self._app("[resources.widgets.roles]\npost = []\n", resource=resource)
        self.assertEqual(
            app.post("/widgets", headers=_auth(roles=["admin"]), expect_errors=True).status_code,
            405,
        )

    def test_emptyList_onClass_turnsMethodOff(self):
        resource = _makeResource()
        resource.POST = {"roles": []}
        _, app = self._app(resource=resource)
        self.assertEqual(app.post("/widgets", expect_errors=True).status_code, 405)

    def test_emptyList_dbResource_writesOff(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=self._writeCfg(
                f'sqlite = "{tmp_db}"\ndefault_roles = true\n'
                "[resources.animals.roles]\npost = []\nput = []\npatch = []\ndelete = []\n"
            ),
            gen_res=False, gen_db=True,
        )
        app = webtest.TestApp(bs)
        self.assertEqual(app.get("/animals", headers=_auth()).status_code, 200)
        for path in ("/animals", "/animals/1"):
            for meth in ("post", "put", "patch", "delete"):
                resp = getattr(app, meth)(path, headers=_auth(), expect_errors=True)
                self.assertEqual(resp.status_code, 405, f"{meth} {path}")

    def test_optionsStaysOpen(self):
        _, app = self._app("default_roles = true\n")
        self.assertEqual(app.options("/widgets").status_code, 200)

    def test_listDefault_copiedPerRoute(self):
        resource = _makeResource()
        self._app('default_roles = ["admin"]\n', resource=resource)
        get_roles = resource.getRouteConfig(resource.Methods.GET)["roles"]
        post_roles = resource.getRouteConfig(resource.Methods.POST)["roles"]
        self.assertEqual(get_roles, ["admin"])
        self.assertIsNot(get_roles, post_roles)

    def test_builtinMetaRoutes_requireAdminRole(self):
        # default_roles doesn't apply to the meta routes: only the
        # dashboard's ADMIN_ROLE gets in, whatever the app's own roles.
        _, app = self._app('default_roles = ["admin"]\n', dashboard=True)
        for roles in (["viewer"], ["admin"]):
            self.assertEqual(
                app.get("/_roles", headers=_auth(roles=roles), expect_errors=True).status_code,
                403,
            )
        self.assertEqual(app.get("/_roles", headers=_auth(roles=[ADMIN_ROLE])).status_code, 200)

    def test_builtinMetaRoutes_tomlRolesAddToAdminRole(self):
        _, app = self._app('[resources._roles.roles]\nget = ["admin"]\n', dashboard=True)
        self.assertEqual(app.get("/_roles", headers=_auth(roles=["admin"])).status_code, 200)
        self.assertEqual(app.get("/_roles", headers=_auth(roles=[ADMIN_ROLE])).status_code, 200)
        self.assertEqual(
            app.get("/_roles", headers=_auth(roles=["viewer"]), expect_errors=True).status_code,
            403,
        )

    def test_builtinMetaRoutes_tomlBoolCantOpenThem(self):
        for value in ("false", "true"):
            _, app = self._app(f"[resources._roles.roles]\nget = {value}\n", dashboard=True)
            self.assertEqual(app.get("/_roles", expect_errors=True).status_code, 400)
            self.assertEqual(
                app.get("/_roles", headers=_auth(roles=["viewer"]), expect_errors=True).status_code,
                403,
            )

    def test_builtinMetaRoutes_absentWithoutDashboard(self):
        _, app = self._app("default_roles = true\n")
        for path in ("/_roles", "/_resources", "/_python_resources", "/_datatypes", "/bottler_cfg"):
            self.assertEqual(
                app.get(path, headers=_auth(roles=[ADMIN_ROLE]), expect_errors=True).status_code,
                404,
            )

    def test_dbResources_getDefault(self):
        tmp_db = db_fixtures.temp_sqlite_copy()
        self.addCleanup(os.remove, tmp_db)
        bs = Bottler(
            cfg_file=self._writeCfg(f'sqlite = "{tmp_db}"\ndefault_roles = true\n'),
            gen_res=False, gen_db=True,
        )
        app = webtest.TestApp(bs)
        self.assertEqual(app.get("/animals", expect_errors=True).status_code, 400)
        self.assertEqual(app.get("/animals", headers=_auth()).status_code, 200)


class TestBuildRoles(unittest.TestCase):
    def test_unsetMethodsShowDefault(self):
        roles = {r["method"]: r["roles"] for r in _buildRoles({"roles": {"get": False}}, True)}
        self.assertEqual(roles["get"], False)
        self.assertEqual(roles["post"], True)

    def test_noDefault_unsetMethodsFalse(self):
        roles = {r["method"]: r["roles"] for r in _buildRoles({})}
        self.assertTrue(all(v is False for v in roles.values()))


if __name__ == "__main__":
    unittest.main()
