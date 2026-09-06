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


def createResource(name, fields, sql=False):
    class ChildResource(Resource):
        key = next((f["name"] for f in fields if f["key"] == 1), None)
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
                    sql = f"select * from {ref_table} where {ref_col}={self.bind_char}"
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
            sql = f"""SELECT * FROM {name}"""
            if key:
                bindings += (key,)
                sql += f" WHERE {self.key}={self.bind_char}"
            elif self.params:
                bindings = tuple(f"%{v}%" for v in self.params.values())
                filters = " AND ".join(
                    [f"{k} LIKE {self.bind_char}" for k in self.params.keys()]
                )
                sql += f" WHERE {filters}"
            query = db.execute(sql, bindings)
            try:
                rows = query.fetchone() if key else query.fetchall()
            except:
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

        def _doPost(self, db, **kwargs):
            if self.key in kwargs and not kwargs[self.key]:
                kwargs.pop(self.key)
            bindings = tuple(kwargs.values())
            sql = f"""INSERT INTO {self.table} ({','.join(kwargs.keys())})
                        VALUES ({','.join([self.bind_char for x in range(len(bindings))])})"""
            try:
                executed = db.execute(sql, bindings)
            except SqlIntegrityError as e:
                response.status = 422
                return {"message": str(e)}
            except SqliteIntegrityError as e:
                response.status = 422
                parts = str(e).split(".")
                message = f"{parts[1]} must be unique" if len(parts) > 1 else str(e)
                return {"message": message}
            # Get row ID of created resource
            try:
                last_row_id = executed.lastrowid
            except AttributeError:
                last_row_id = db.lastrowid
            created = self.get(db, last_row_id)
            response.status = 201
            return created

        def _doPut(self, db, **kwargs):
            res_id = kwargs.pop(self.key)
            bindings = tuple(kwargs.values())
            sql = f"""UPDATE {self.table}
                      SET {','.join([f'{k}={self.bind_char}' for k in kwargs])}
                      WHERE {self.key}={self.bind_char}"""
            bindings += (res_id,)
            try:
                db.execute(sql, bindings)
                updated = self.get(db, res_id)
                response.status = 200
                return updated
            except Exception as e:
                response.status = 500
                return {"message": f"{type(e)} {e}"}

        def _doPatch(self, db, **kwargs):
            res_id = kwargs.pop(self.key)
            bindings = tuple(v for v in kwargs.values() if v != PatchData.UNCHANGED)
            sql = f"""UPDATE {self.table}
                      SET {','.join([f'{k}={self.bind_char}' for k, v in kwargs.items() if v != PatchData.UNCHANGED])}
                      WHERE {self.key}={self.bind_char}"""
            bindings += (res_id,)
            try:
                db.execute(sql, bindings)
                updated = self.get(db, res_id)
                response.status = 200
                return updated
            except Exception as e:
                response.status = 500
                return {"message": f"{type(e)} {e}"}

        def delete(self, db, key):
            sql = f"DELETE FROM {self.table} WHERE {self.key}={self.bind_char}"
            try:
                db.execute(sql, (key,))
                response.status = 200
                return {"message": f"{self.key} {key} deleted"}
            except Exception as e:
                response.status = 500
                return {"message": f"{type(e)} {e}"}

        @classmethod
        def createFunction(cls, _name: str, *args, key_param: str = None, **kwargs):
            params = ""
            _args = ""
            if args:
                outer_names = ["key" if a == key_param else a for a in args]
                params += f", {', '.join(outer_names)}"
                _args += "," + ", ".join(
                    [f"{a}=key" if a == key_param else f"{a}={a}" for a in args]
                )
            if kwargs:
                params += ", " + ", ".join([f"{x}={kwargs[x]}" for x in kwargs])
                _args += ", " + ", ".join([f"{x}={x}" for x in kwargs])
            exec(
                f"""def func(self, db{params}):
                return self._do{_name.capitalize()}(db{_args})"""
            )
            setattr(cls, _name.lower(), locals().get("func"))

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
