from .plugins import Resource
from bottle import response
from pymysql import IntegrityError as SqlIntegrityError
from sqlite3 import IntegrityError as SqliteIntegrityError
from enum import Enum
import re
from typing import Union


FOREIGN_KEY_SQL = """
    select distinct
        c.table_name,
        c.column_name,
        c.referenced_table_name, 
        c.referenced_column_name 
    from information_schema.table_constraints fk
    join information_schema.key_column_usage c 
    on c.constraint_name = fk.constraint_name
    where fk.constraint_type = 'FOREIGN KEY'
        and c.table_name = 
"""
REPLACE_TEXT = ["_id", "_ID", "_iD", "-id", "-ID", "-iD", "id", "ID", "Id"]


class PatchData(Enum):
    UNCHANGED = 1


def q(identifier: str) -> str:
    """Backtick-quote a table/column name for generated SQL (both MySQL and
    sqlite accept backticks), so names like "401k_amount" or keywords like
    "from" are valid identifiers."""
    return "`" + identifier.replace("`", "``") + "`"


def createResource(name, fields, sql=False):
    class ChildResource(Resource):
        key = next((f["name"] for f in fields if f["key"] == 1), None)
        field_names = {f["name"] for f in fields}
        bind_char = "%s" if sql else "?"
        table = name
        _name = "".join([x.capitalize() for x in re.split(", |_|-|!", name)])
        refs = {}  # reference table cache

        def getRefs(self, db, table, row: dict = None, levels=1) -> Union[dict, None]:
            if levels <= 1 and row:
                return None
            levels -= 1
            _refs = self.refs.get(table)  # Get cached references
            if not _refs:
                if self.bind_char == "?":  # sqlite has no information_schema
                    db.execute(f"PRAGMA foreign_key_list('{table}')")
                    _refs = [
                        {
                            "table_name": table,
                            "column_name": r["from"],
                            "referenced_table_name": r["table"],
                            "referenced_column_name": r["to"],
                        }
                        for r in db.fetchall()
                    ]
                else:
                    db.execute(FOREIGN_KEY_SQL + f"'{table}'")
                    _refs = db.fetchall()
                self.refs[table] = _refs
            if row:
                for ref in _refs:
                    _, col, ref_table, ref_col = tuple(ref.values())
                    if not row[col]:
                        continue
                    sql = f"select * from {q(ref_table)} where {q(ref_col)}={self.bind_char}"
                    db.execute(sql, (row[col],))
                    row.pop(col)
                    for t in REPLACE_TEXT:
                        col = col.replace(t, "")
                    ref_row = db.fetchone()
                    self.getRefs(db, ref_table, ref_row, levels)
                    row[col] = ref_row
            return _refs

        def options(self):
            pass

        def get(self, db, key=None, ref_table=None, ref_id=None):
            if ref_table:
                _refs = self.getRefs(db, name)
                # Matches by referenced table name only -- if this table has
                # more than one FK to ref_table (e.g. predator/prey both
                # referencing animals), this always picks the first one
                # found and can't disambiguate which column the caller meant.
                ref_col = next(
                    (r for r in _refs if r["referenced_table_name"] == ref_table),
                    {},
                ).get("column_name")
                if ref_col:
                    self.params[ref_col] = ref_id
                else:
                    response.status = 404
                    return {"message": "Resource not found"}
            levels = int(self.params.pop("levels", 1))
            bindings = ()
            sql = f"""SELECT * FROM {q(name)}"""
            if key:
                bindings += (key,)
                sql += f" WHERE {q(self.key)}={self.bind_char}"
            elif self.params:
                # self.params is request.params -- arbitrary query-string
                # keys. Only bind the values; validate the keys against the
                # table's real columns before they're concatenated into SQL.
                unknown = [k for k in self.params if k not in self.field_names]
                if unknown:
                    response.status = 400
                    return {"message": f"Unknown filter field(s): {', '.join(unknown)}"}
                bindings = tuple(f"%{v}%" for v in self.params.values())
                filters = " AND ".join(
                    [f"{q(k)} LIKE {self.bind_char}" for k in self.params.keys()]
                )
                sql += f" WHERE {filters}"
            query = db.execute(sql, bindings)
            try:
                rows = query.fetchone() if key else query.fetchall()
            except AttributeError:
                rows = db.fetchone() if key else db.fetchall()
            if rows or not key:
                if isinstance(rows, tuple):
                    rows = list(rows)
                if isinstance(rows, list):
                    for row in rows:
                        self.getRefs(db, name, row, levels)
                    rows = {name: rows}
                else:
                    self.getRefs(db, name, rows, levels)
                return rows
            else:
                response.status = 404
                return {"message": "Resource not found"}

        @staticmethod
        def _integrityErrorMessage(e):
            if isinstance(e, SqlIntegrityError):
                return str(e)
            parts = str(e).split(".")
            return f"{parts[1]} must be unique" if len(parts) > 1 else str(e)

        def _runMutation(self, action):
            # Shared try/except shape for _doPost/_doPut/_doPatch/delete: a
            # unique-constraint violation is always a clean 422 (not just on
            # create), anything else is a 500.
            try:
                return action()
            except (SqlIntegrityError, SqliteIntegrityError) as e:
                response.status = 422
                return {"message": self._integrityErrorMessage(e)}
            except Exception as e:
                response.status = 500
                return {"message": f"{type(e)} {e}"}

        def _doPost(self, db, **kwargs):
            if self.key in kwargs and not kwargs[self.key]:
                kwargs.pop(self.key)
            bindings = tuple(kwargs.values())
            sql = f"""INSERT INTO {q(self.table)} ({','.join(q(k) for k in kwargs)})
                        VALUES ({','.join([self.bind_char for x in range(len(bindings))])})"""

            def _create():
                executed = db.execute(sql, bindings)
                # Get row ID of created resource
                try:
                    last_row_id = executed.lastrowid
                except AttributeError:
                    last_row_id = db.lastrowid
                created = self.get(db, last_row_id)
                response.status = 201
                return created

            return self._runMutation(_create)

        def _doPut(self, db, **kwargs):
            res_id = kwargs.pop(self.key)
            bindings = tuple(kwargs.values())
            sql = f"""UPDATE {q(self.table)}
                      SET {','.join([f'{q(k)}={self.bind_char}' for k in kwargs])}
                      WHERE {q(self.key)}={self.bind_char}"""
            bindings += (res_id,)

            def _update():
                db.execute(sql, bindings)
                updated = self.get(db, res_id)
                response.status = 200
                return updated

            return self._runMutation(_update)

        def _doPatch(self, db, **kwargs):
            res_id = kwargs.pop(self.key)
            bindings = tuple(v for v in kwargs.values() if v != PatchData.UNCHANGED)
            sql = f"""UPDATE {q(self.table)}
                      SET {','.join([f'{q(k)}={self.bind_char}' for k, v in kwargs.items() if v != PatchData.UNCHANGED])}
                      WHERE {q(self.key)}={self.bind_char}"""
            bindings += (res_id,)

            def _update():
                db.execute(sql, bindings)
                updated = self.get(db, res_id)
                response.status = 200
                return updated

            return self._runMutation(_update)

        def delete(self, db, key):
            sql = f"DELETE FROM {q(self.table)} WHERE {q(self.key)}={self.bind_char}"

            def _delete():
                db.execute(sql, (key,))
                response.status = 200
                return {"message": f"{self.key} {key} deleted"}

            return self._runMutation(_delete)

        @classmethod
        def createFunction(cls, _name: str, *args, key_param: str = None, **kwargs):
            # Column names can't be Python parameter names (e.g. "401k_amount"
            # is not a valid identifier), so fields arrive through **fields and
            # the required/unknown checks the REST plugin would otherwise do
            # from the signature are done here. *args are required fields,
            # **kwargs optional fields with defaults; key_param (if any) is
            # taken from the "<key>" URL param instead of the request body.
            required = [a for a in args if a != key_param]
            allowed = set(args) | set(kwargs)
            do = getattr(cls, f"_do{_name.capitalize()}")

            def run(self, db, fields):
                unknown = [f for f in fields if f not in allowed]
                if unknown:
                    response.status = 400
                    return {"message": f"Unknown field(s): {', '.join(unknown)}"}
                missing = next((a for a in required if a not in fields), None)
                if missing:
                    response.status = 400
                    return {missing: "This field is required"}
                for k, v in kwargs.items():
                    fields.setdefault(k, v)
                return do(self, db, **fields)

            if key_param:

                def func(self, db, key, **fields):
                    fields[key_param] = key
                    return run(self, db, fields)

            else:

                def func(self, db, **fields):
                    return run(self, db, fields)

            setattr(cls, _name.lower(), func)

    ChildResource.createFunction(
        "post",
        *[f["name"] for f in fields if f["name"] != ChildResource.key],
        **{ChildResource.key: None},
    )
    ChildResource.createFunction(
        "put",
        *[f["name"] for f in fields],
        key_param=ChildResource.key,
    )
    ChildResource.createFunction(
        "patch",
        ChildResource.key,
        key_param=ChildResource.key,
        **{
            f["name"]: PatchData.UNCHANGED
            for f in fields
            if f["name"] != ChildResource.key
        },
    )
    return ChildResource
