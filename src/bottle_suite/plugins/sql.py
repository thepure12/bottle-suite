# Vendored from bottle-sql (https://github.com/thepure12/bottle-sql), MIT License.
# SQLite engine-selection bug fixed (see Engine.SQLITE branch).
from enum import Enum
import bottle
import inspect

__author__ = "TJ Renninger"
__license__ = "MIT"


class Engine(Enum):
    SQL = 1
    SQLITE = 2


class SQLPlugin:
    name = "bottle_sql"
    api = 2

    def __init__(
        self,
        engine: Engine = Engine.SQL,
        sql_config=None,
        dictrows=True,
        autocommit=True,
        keyword="db",
    ) -> None:
        self.sql_config = sql_config
        self.autocommit = autocommit
        self.keyword = keyword
        if engine == Engine.SQL:
            import pymysql
            import pymysql.cursors

            self.engine = pymysql
            if dictrows:
                self.sql_config["cursorclass"] = pymysql.cursors.DictCursor
        elif engine == Engine.SQLITE:
            import sqlite3

            class MyConnection(sqlite3.Connection):
                def __init__(self, **kwargs) -> None:
                    super().__init__(**kwargs)
                    if dictrows:
                        self.row_factory = lambda cursor, row: {
                            col[0]: row[idx]
                            for idx, col in enumerate(cursor.description)
                        }

            self.engine = sqlite3
            self.sql_config["factory"] = MyConnection

    def setup(self, app):
        for plugin in app.plugins:
            if not isinstance(plugin, SQLPlugin):
                continue
            if plugin.keyword == self.keyword:
                raise bottle.PluginError(
                    "Found another SQL plugin with conflicting settings (non-unique keyword)."
                )

    def apply(self, callback, route):
        # hack to support bottle v0.9.x
        if bottle.__version__.startswith("0.9"):
            config = route["config"]
            _callback = route["callback"]
        else:
            config = route.config
            _callback = route.callback

        # Override global configuration with route-specific values.
        if "bottle_sql" in config:
            # support for configuration before `ConfigDict` namespaces
            g = lambda key, default: config.get("bottle_sql", {}).get(key, default)
        else:
            g = lambda key, default: config.get("bottle_sql." + key, default)

        keyword = g("keyword", self.keyword)

        args = inspect.signature(_callback).parameters
        if keyword not in args:
            return callback

        _sql_config = {k: g(k, v) for k, v in self.sql_config.items()}
        autocommit = g("autocommit", self.autocommit)

        def wrapper(*args, **kwargs):
            conn = self.engine.connect(**_sql_config)
            db = conn.cursor()
            kwargs[keyword] = db
            try:
                rv = callback(*args, **kwargs)
                if autocommit:
                    conn.commit()
            except self.engine.IntegrityError as e:
                conn.rollback()
                raise bottle.HTTPError(500, "Database Error", e)
            except bottle.HTTPError as e:
                raise
            except bottle.HTTPResponse as e:
                if autocommit:
                    conn.commit()
                raise
            finally:
                conn.close()
            return rv

        return wrapper


def sqlPlugin(
    user=None, password="", host=None, database=None, dictrows=True
) -> SQLPlugin:
    return SQLPlugin(
        Engine.SQL,
        {"user": user, "password": password, "host": host, "database": database},
        dictrows=dictrows,
    )


def sqlitePlugin(database, dictrows=True) -> SQLPlugin:
    return SQLPlugin(
        Engine.SQLITE, sql_config={"database": database}, dictrows=dictrows
    )
