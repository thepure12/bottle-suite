import _paths  # noqa: F401
import os
import shutil
import sqlite3
import sys
import tempfile
import textwrap
import unittest
from datetime import datetime, timedelta

import jwt as pyjwt
import webtest

from bottler import Bottler
from bottler.dashboard.resources.token import ADMIN_ROLE

JWT_KEY = "mount-secret"

# One resource module whose name ("items") is used by both packages, so the
# tests prove two mounted packages can share resource names. It reads from the
# injected `db`, which only works if the child's own SQL plugin runs.
ITEMS_RESOURCE = '''
from bottler import Resource


class Items(Resource):
    def options(self):
        pass

    def get(self, db):
        db.execute("SELECT name FROM items")
        return {"items": [r["name"] for r in db.fetchall()]}
'''

# Same items table, but a hand-written resource that takes `key`, like a
# connector's own CRUD resource for one of its tables.
KEYED_ITEMS_RESOURCE = '''
from bottler import Resource


class Items(Resource):
    def options(self):
        pass

    def get(self, key=None):
        return {"hand": key}

    def patch(self, key, **fields):
        return {"hand": key}
'''

ADMIN_RESOURCE = '''
from bottler import Resource


class Admin(Resource):
    GET = {"roles": ["admin"]}

    def options(self):
        pass

    def get(self):
        return {"ok": True}
'''

PACKAGE_INIT = '''
configured = []


def configure(app):
    configured.append(app.base_dir)
'''


def _token(**claims):
    payload = {"exp": datetime.utcnow() + timedelta(days=1), **claims}
    return pyjwt.encode(payload, JWT_KEY, algorithm="HS256")


def _auth(**claims):
    return {"Authorization": f"Bearer {_token(**claims)}"}


class TestMounts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        sys.path.insert(0, self.tmp)
        self.addCleanup(sys.path.remove, self.tmp)
        self.packages = []
        self.addCleanup(self._purgePackages)

    def _purgePackages(self):
        for name in list(sys.modules):
            if name.split(".")[0] in self.packages:
                del sys.modules[name]

    def _package(self, name, rows, extra_cfg="", init=PACKAGE_INIT, admin=False, items=ITEMS_RESOURCE):
        """A package <name> with resources/items.py, plus its config folder
        <tmp>/cfg/<name> holding bottler.toml and a sqlite DB whose
        items table contains `rows`."""
        self.packages.append(name)
        res_dir = os.path.join(self.tmp, name, "resources")
        os.makedirs(res_dir)
        with open(os.path.join(self.tmp, name, "__init__.py"), "w") as f:
            f.write(init)
        with open(os.path.join(res_dir, "__init__.py"), "w") as f:
            f.write("")
        with open(os.path.join(res_dir, "items.py"), "w") as f:
            f.write(items)
        if admin:
            with open(os.path.join(res_dir, "admin.py"), "w") as f:
                f.write(ADMIN_RESOURCE)
        cfg_dir = os.path.join(self.tmp, "cfg", name)
        os.makedirs(cfg_dir)
        db_path = os.path.join(cfg_dir, "data.db")
        con = sqlite3.connect(db_path)
        con.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
        con.executemany("INSERT INTO items (name) VALUES (?)", [(r,) for r in rows])
        con.commit()
        con.close()
        with open(os.path.join(cfg_dir, "bottler.toml"), "w") as f:
            f.write(f'sqlite = "{db_path}"\n' + textwrap.dedent(extra_cfg))
        return cfg_dir

    def _host(self, mounts_toml, extra=""):
        os.makedirs(os.path.join(self.tmp, "cfg"), exist_ok=True)
        cfg = os.path.join(self.tmp, "cfg", "bottler.toml")
        with open(cfg, "w") as f:
            f.write(f'jwt = "{JWT_KEY}"\n{extra}\n' + textwrap.dedent(mounts_toml))
        bs = Bottler(cfg_file=cfg, gen_res=False, gen_auth=False, gen_hooks=False)
        return bs, webtest.TestApp(bs)

    def test_each_mount_uses_its_own_database(self):
        self._package("pkg_a", ["a1", "a2"])
        self._package("pkg_b", ["b1"])
        bs, app = self._host('''
            [mounts.a]
            package = "pkg_a"
            base_dir = "pkg_a"

            [mounts.b]
            package = "pkg_b"
            base_dir = "pkg_b"
        ''')
        self.assertEqual(app.get("/a/items").json, {"items": ["a1", "a2"]})
        self.assertEqual(app.get("/b/items").json, {"items": ["b1"]})
        self.assertEqual(set(bs.mounts), {"a", "b"})

    def test_string_entry_and_default_base_dir(self):
        self._package("pkg_c", ["c1"])
        # base_dir defaults to the mount name, so name the mount after the
        # config folder.
        _, app = self._host('[mounts]\npkg_c = "pkg_c"\n')
        self.assertEqual(app.get("/pkg_c/items").json, {"items": ["c1"]})

    def test_db_auto_crud_is_per_mount(self):
        self._package("pkg_d", ["d1"])
        _, app = self._host('[mounts.d]\npackage = "pkg_d"\nbase_dir = "pkg_d"\n')
        # items.py (hand-written) wins /items; the generated /items/<id>
        # route still comes from this mount's own DB.
        self.assertEqual(app.get("/d/items/1").json["name"], "d1")

    def test_hand_resource_taking_key_wins_keyed_route(self):
        # Without toml paths, a hand-written resource whose methods take
        # `key` gets /items/<key> too, so the generated route for the items
        # table never answers it.
        self._package("pkg_k", ["k1"], items=KEYED_ITEMS_RESOURCE)
        _, app = self._host('[mounts.k]\npackage = "pkg_k"\nbase_dir = "pkg_k"\n')
        self.assertEqual(app.get("/k/items/1").json, {"hand": "1"})
        self.assertEqual(app.patch_json("/k/items/1", {"name": "x"}).json, {"hand": "1"})
        # The generated PUT isn't on that path either.
        self.assertEqual(
            app.put_json("/k/items/1", {"name": "x"}, expect_errors=True).status_code, 405
        )

    def test_api_prefix_applies_to_mounts(self):
        self._package("pkg_e", ["e1"])
        _, app = self._host(
            '[mounts.e]\npackage = "pkg_e"\nbase_dir = "pkg_e"\n', extra='api_prefix = "api"'
        )
        self.assertEqual(app.get("/api/e/items").json, {"items": ["e1"]})
        self.assertEqual(app.get("/e/items", expect_errors=True).status_code, 404)

    def test_parent_token_and_default_roles_apply_in_mount(self):
        self._package("pkg_f", ["f1"])
        _, app = self._host(
            '[mounts.f]\npackage = "pkg_f"\nbase_dir = "pkg_f"\n',
            extra='default_roles = ["finance"]',
        )
        self.assertEqual(app.get("/f/items", expect_errors=True).status_code, 400)
        self.assertEqual(
            app.get("/f/items", headers=_auth(roles=["interns"]), expect_errors=True).status_code,
            403,
        )
        ok = app.get("/f/items", headers=_auth(roles=["finance"]))
        self.assertEqual(ok.json, {"items": ["f1"]})

    def test_child_toml_cannot_override_inherited_settings(self):
        self._package("pkg_g", ["g1"], extra_cfg='jwt = "other-key"\napi_prefix = "nested"\n')
        _, app = self._host(
            '[mounts.g]\npackage = "pkg_g"\nbase_dir = "pkg_g"\n', extra="default_roles = true"
        )
        # Parent's key is accepted (the child's own "other-key" is ignored),
        # and the child's api_prefix doesn't nest under the mount.
        self.assertEqual(app.get("/g/items", headers=_auth()).json, {"items": ["g1"]})

    def test_child_toml_default_roles_and_resource_roles(self):
        self._package(
            "pkg_h", ["h1"],
            extra_cfg='default_roles = ["admin"]\n[resources.items.roles]\nget = ["viewer"]\n',
        )
        _, app = self._host('[mounts.h]\npackage = "pkg_h"\nbase_dir = "pkg_h"\n')
        self.assertEqual(
            app.get("/h/items", headers=_auth(roles=["admin"]), expect_errors=True).status_code,
            403,
        )
        self.assertEqual(app.get("/h/items", headers=_auth(roles=["viewer"])).status_code, 200)

    def test_only_parent_issues_tokens(self):
        self._package("pkg_i", ["i1"])
        _, app = self._host('[mounts.i]\npackage = "pkg_i"\nbase_dir = "pkg_i"\n')
        self.assertEqual(app.post_json("/token", {}).status_code, 200)
        self.assertEqual(app.post_json("/i/token", {}, expect_errors=True).status_code, 404)

    def test_roles_do_not_pile_up_on_cached_classes(self):
        self._package(
            "pkg_j", ["j1"], admin=True,
            extra_cfg='[resources.admin.roles]\nget = ["finance"]\n',
        )
        mounts = '[mounts.j]\npackage = "pkg_j"\nbase_dir = "pkg_j"\n'
        self._host(mounts)
        bs, app = self._host(mounts)
        admin_cls = sys.modules["pkg_j.resources.admin"].Admin
        self.assertEqual(admin_cls.GET["roles"], ["admin", "finance"])
        self.assertEqual(app.get("/j/admin", headers=_auth(roles=["finance"])).json, {"ok": True})

    def test_package_configure_hook_gets_base_dir(self):
        cfg_dir = self._package("pkg_k", ["k1"])
        self._host('[mounts.k]\npackage = "pkg_k"\nbase_dir = "pkg_k"\n')
        self.assertEqual(sys.modules["pkg_k"].configured, [cfg_dir])

    def test_package_without_configure_hook(self):
        self._package("pkg_l", ["l1"], init="")
        _, app = self._host('[mounts.l]\npackage = "pkg_l"\nbase_dir = "pkg_l"\n')
        self.assertEqual(app.get("/l/items").json, {"items": ["l1"]})

    def test_invalid_mount_name_rejected(self):
        with self.assertRaisesRegex(Exception, "Invalid mount name"):
            self._host('[mounts."../x"]\npackage = "nope"\n')

    def test_mounts_require_rest(self):
        self._package("pkg_m", ["m1"])
        with self.assertRaisesRegex(Exception, "mounts require rest"):
            self._host('rest = false\n[mounts.m]\npackage = "pkg_m"\nbase_dir = "pkg_m"\n')

    def test_mounts_without_jwt_or_cfg_file(self):
        self._package("pkg_n", ["n1"])
        cwd = os.getcwd()
        os.chdir(os.path.join(self.tmp, "cfg"))
        self.addCleanup(os.chdir, cwd)
        bs = Bottler(
            cfg_file=None, jwt=False, gen_res=False, gen_auth=False, gen_hooks=False,
            mounts={"pkg_n": "pkg_n"},
        )
        app = webtest.TestApp(bs)
        self.assertEqual(app.get("/pkg_n/items").json, {"items": ["n1"]})

    def test_standalone_package_app_without_mounting(self):
        # A package app on its own (e.g. a connector repo's dev server builds
        # it directly): its own toml applies, nothing is inherited.
        cfg_dir = self._package("pkg_o", ["o1"], extra_cfg=f'jwt = "{JWT_KEY}"\n')
        bs = Bottler(package="pkg_o", base_dir=cfg_dir, gen_hooks=False)
        app = webtest.TestApp(bs)
        self.assertEqual(app.get("/items").json, {"items": ["o1"]})
        # Package mode never looks for a cwd auth.py, so /token keeps the
        # default auth function.
        self.assertEqual(app.post_json("/token", {}).status_code, 200)

    def test_mounted_child_has_no_meta_routes(self):
        # Even with the dashboard on in the host, a child's config, tables
        # and roles are never exposed through the meta/admin routes.
        self._package("pkg_p", ["p1"])
        _, app = self._host('''
            [mounts.p]
            package = "pkg_p"
            base_dir = "pkg_p"
        ''', extra="dashboard = true")
        headers = _auth(roles=[ADMIN_ROLE])
        self.assertEqual(app.get("/_roles", headers=headers).status_code, 200)
        for path in ("/p/bottler_cfg", "/p/_resources", "/p/_python_resources", "/p/_roles"):
            self.assertEqual(app.get(path, headers=headers, expect_errors=True).status_code, 404)


if __name__ == "__main__":
    unittest.main()
