"""Shared helpers for mocking pymysql, since no live MySQL server is
available in this environment. Patching pymysql.connect globally is
sufficient because both bottle_suite.py and plugins/sql.py call it as a
direct module attribute (no per-module re-import to chase).
"""
import unittest.mock as mock
import pymysql
import pymysql.cursors
import pymysql.err


def make_mysql_cursor(fetchone=None, fetchall=None, lastrowid=1,
                       execute_returns=1, execute_side_effect=None):
    """Build a cursor mock that behaves like pymysql's DictCursor.

    spec=pymysql.cursors.DictCursor is required: bottle_suite.getDBTables()
    does `isinstance(db, pymysql.cursors.Cursor)` with no fallback branch,
    so an un-spec'd MagicMock would fail that check silently.

    execute() defaults to returning an int (matching real pymysql/DBAPI
    rowcount semantics), unlike sqlite3.Cursor.execute() which returns
    self -- this is what makes resource_factory's fallback branches
    (`except: rows = db.fetchone()/fetchall()`,
    `except AttributeError: last_row_id = db.lastrowid`) actually run.
    """
    cursor = mock.MagicMock(spec=pymysql.cursors.DictCursor)
    cursor.fetchone.return_value = fetchone
    cursor.fetchall.return_value = fetchall if fetchall is not None else []
    cursor.lastrowid = lastrowid
    if execute_side_effect is not None:
        cursor.execute.side_effect = execute_side_effect
    else:
        cursor.execute.return_value = execute_returns
    return cursor


def pragma_raises_side_effect():
    """execute() side_effect that rejects PRAGMA statements (mimicking real
    MySQL rejecting sqlite syntax) and otherwise returns 1, so
    getDBTable()'s `try PRAGMA / except DESCRIBE` fallback is exercised.
    """
    def _side_effect(sql, *a, **kw):
        if sql.strip().upper().startswith("PRAGMA"):
            raise pymysql.err.ProgrammingError("You have an error in your SQL syntax")
        return 1
    return _side_effect


def patch_pymysql_connect(cursor=None):
    """Returns (patcher, mock_conn, cursor). Start the patcher (as a context
    manager, or via .start()/.stop()). mock_conn exposes assertable
    .commit()/.rollback()/.close() mocks; mock_conn.cursor() returns `cursor`.
    """
    cursor = cursor or make_mysql_cursor()
    mock_conn = mock.MagicMock()
    mock_conn.cursor.return_value = cursor
    patcher = mock.patch("pymysql.connect", return_value=mock_conn)
    return patcher, mock_conn, cursor
