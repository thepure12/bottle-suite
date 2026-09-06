import _paths  # noqa: F401
import unittest
from unittest import mock
import bottle
import pymysql
import pymysql.err
from bottle_suite.plugins.sql import SQLPlugin, Engine, sqlPlugin, sqlitePlugin
from mysql_mock import make_mysql_cursor, patch_pymysql_connect


class FakeRoute:
    """Minimal object exposing .config / .callback, matching what
    SQLPlugin.apply() reads off a real bottle.Route."""

    def __init__(self, config, callback):
        self.config = config
        self.callback = callback


def apply_and_call(plugin, callback, config=None, args=(), kwargs=None):
    route = FakeRoute(config or {}, callback)
    wrapped = plugin.apply(callback, route)
    return wrapped(*args, **(kwargs or {}))


class TestSQLPlugin(unittest.TestCase):
    def setUp(self):
        self.cursor = make_mysql_cursor(fetchall=[{"id": 1}])
        self.patcher, self.mock_conn, self.cursor = patch_pymysql_connect(self.cursor)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.plugin = SQLPlugin(
            Engine.SQL,
            {"user": "u", "password": "p", "host": "h", "database": "d"},
        )

    def test_commit_onSuccess(self):
        def cb(db):
            return {"ok": True}

        result = apply_and_call(self.plugin, cb, config={})
        self.assertEqual(result, {"ok": True})
        self.mock_conn.commit.assert_called_once()
        self.mock_conn.close.assert_called_once()

    def test_rollback_onIntegrityError_raisesHTTPError(self):
        self.cursor.execute.side_effect = pymysql.IntegrityError("dup")

        def cb(db):
            db.execute("insert ...")
            return {"ok": True}

        with self.assertRaises(bottle.HTTPError):
            apply_and_call(self.plugin, cb, config={})
        self.mock_conn.rollback.assert_called_once()
        self.mock_conn.close.assert_called_once()

    def test_otherOperationalError_propagatesUncaught(self):
        self.cursor.execute.side_effect = pymysql.err.OperationalError("gone away")

        def cb(db):
            db.execute("select 1")
            return {"ok": True}

        with self.assertRaises(pymysql.err.OperationalError):
            apply_and_call(self.plugin, cb, config={})
        self.mock_conn.close.assert_called_once()

    def test_httpError_raised_noCommit(self):
        def cb(db):
            raise bottle.HTTPError(404, "nope")

        with self.assertRaises(bottle.HTTPError):
            apply_and_call(self.plugin, cb, config={})
        self.mock_conn.commit.assert_not_called()
        self.mock_conn.close.assert_called_once()

    def test_httpResponse_raised_commitsThenReraises(self):
        def cb(db):
            raise bottle.HTTPResponse(body="ok", status=200)

        with self.assertRaises(bottle.HTTPResponse):
            apply_and_call(self.plugin, cb, config={})
        self.mock_conn.commit.assert_called_once()
        self.mock_conn.close.assert_called_once()

    def test_callbackWithoutDbKeyword_bypassesWrapping(self):
        def cb():
            return "untouched"

        route = FakeRoute({}, cb)
        wrapped = self.plugin.apply(cb, route)
        self.assertIs(wrapped, cb)
        self.mock_conn.cursor.assert_not_called()

    def test_routeConfigOverride_legacyDictStyle(self):
        def cb(other_db):
            return other_db is self.cursor

        result = apply_and_call(
            self.plugin, cb, config={"bottle_sql": {"keyword": "other_db"}}
        )
        self.assertTrue(result)

    def test_routeConfigOverride_dottedKeyStyle(self):
        def cb(other_db):
            return other_db is self.cursor

        result = apply_and_call(
            self.plugin, cb, config={"bottle_sql.keyword": "other_db"}
        )
        self.assertTrue(result)

    def test_routeConfigOverride_autocommitFalse(self):
        def cb(db):
            return {"ok": True}

        apply_and_call(self.plugin, cb, config={"bottle_sql.autocommit": False})
        self.mock_conn.commit.assert_not_called()

    def test_legacyBottle09Compat_routeAsDict(self):
        def cb(db):
            return {"ok": True}

        with mock.patch("bottle.__version__", "0.9.0"):
            wrapped = self.plugin.apply(cb, {"config": {}, "callback": cb})
            result = wrapped()
        self.assertEqual(result, {"ok": True})


    def test_httpResponse_raised_autocommitFalse_noCommit(self):
        plugin = SQLPlugin(
            Engine.SQL,
            {"user": "u", "password": "p", "host": "h", "database": "d"},
            autocommit=False,
        )
        patcher, mock_conn, cursor = patch_pymysql_connect()
        patcher.start()
        self.addCleanup(patcher.stop)

        def cb(db):
            raise bottle.HTTPResponse(body="ok", status=200)

        with self.assertRaises(bottle.HTTPResponse):
            apply_and_call(plugin, cb, config={})
        mock_conn.commit.assert_not_called()


class TestSQLPluginConstructor(unittest.TestCase):
    def test_noSqlConfig_raisesTypeError(self):
        with self.assertRaises(TypeError):
            SQLPlugin(Engine.SQL)

    def test_sqlEngine_dictrowsFalse_skipsCursorclass(self):
        plugin = SQLPlugin(Engine.SQL, {"database": "d"}, dictrows=False)
        self.assertNotIn("cursorclass", plugin.sql_config)

    def test_invalidEngine_neitherBranchTaken_noImmediateCrash(self):
        plugin = SQLPlugin(engine=None, sql_config={})
        self.assertFalse(hasattr(plugin, "engine"))

    def test_sqliteEngine_dictrowsFalse_connectionSkipsRowFactory(self):
        plugin = SQLPlugin(Engine.SQLITE, {"database": ":memory:"}, dictrows=False)
        conn = plugin.engine.connect(**plugin.sql_config)
        try:
            self.assertIsNone(conn.row_factory)
        finally:
            conn.close()

    def test_setup_duplicateKeyword_raisesPluginError(self):
        plugin_a = SQLPlugin(Engine.SQL, {"database": "d"}, keyword="db")
        plugin_b = SQLPlugin(Engine.SQL, {"database": "d"}, keyword="db")

        class FakeApp:
            plugins = [plugin_a]

        with self.assertRaises(bottle.PluginError):
            plugin_b.setup(FakeApp())

    def test_setup_differentKeyword_isNoop(self):
        plugin_a = SQLPlugin(Engine.SQL, {"database": "d"}, keyword="db")
        plugin_b = SQLPlugin(Engine.SQL, {"database": "d"}, keyword="other")

        class FakeApp:
            plugins = [plugin_a]

        plugin_b.setup(FakeApp())  # no raise

    def test_setup_ignoresNonSqlPlugins(self):
        plugin = SQLPlugin(Engine.SQL, {"database": "d"}, keyword="db")

        class FakeApp:
            plugins = [object()]

        plugin.setup(FakeApp())  # no raise


class TestSQLPluginFactories(unittest.TestCase):
    def test_sqlPlugin_factory(self):
        plugin = sqlPlugin(user="u", password="p", host="h", database="d")
        self.assertEqual(plugin.engine.__name__, "pymysql")
        self.assertEqual(plugin.sql_config["database"], "d")

    def test_sqlitePlugin_factory(self):
        plugin = sqlitePlugin(database=":memory:")
        self.assertEqual(plugin.engine.__name__, "sqlite3")
        self.assertEqual(plugin.sql_config["database"], ":memory:")


if __name__ == "__main__":
    unittest.main()
