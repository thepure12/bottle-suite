from bottle_rest import Resource
from bottle import response
from pymysql import IntegrityError as SqlIntegrityError
from sqlite3 import IntegrityError as SqliteIntegrityError
from enum import Enum
import re


class PatchData(Enum):
    UNCHANGED = 1


def createResource(name, fields, sql=False):
    class ChildResource(Resource):
        key = next((f["name"] for f in fields if f["key"] == 1), None)
        bind_char = "%s" if sql else "?"
        table = name
        _name = "".join([x.capitalize() for x in re.split(", |_|-|!", name)])

        def options(self):
            pass

        def get(self, db, key=None):
            bindings = ()
            sql = f"""SELECT * FROM {name}"""
            if key:
                bindings += (key,)
                sql += f" WHERE {self.key}={self.bind_char}"
            elif self.params:
                bindings = tuple(f"%{v}%" for v in self.params.values())
                filters = "AND ".join(
                    [f"{k} LIKE {self.bind_char}" for k in self.params.keys()]
                )
                sql += f" WHERE {filters}"
            query = db.execute(sql, bindings)
            try:
                rows = query.fetchone() if key else {name: query.fetchall()}
            except:
                rows = db.fetchone() if key else {name: db.fetchall()}
            if rows and len(rows):
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
                last_row_id = executed.lastrowid
                created = self.get(db, last_row_id)
                response.status = 201
                return created
            except SqlIntegrityError as e:
                response.status = 422
                return {"message": str(e)}
            except SqliteIntegrityError as e:
                response.status = 422
                return {"message": f"{str(e).split('.')[1]} must be unique"}

        def _doPut(self, db, **kwargs):
            pass

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
            pass

        @classmethod
        def createFunction(cls, _name: str, *args, **kwargs):
            params = ""
            _args = ""
            if args:
                params += f", {', '.join(args)}"
                _args += "," + ", ".join([f"{arg}={arg}" for arg in args])
            if kwargs:
                params += ", " + ", ".join([f"{x}={kwargs[x]}" for x in kwargs])
                _args += ", " + ", ".join([f"{x}={x}" for x in kwargs])
            exec(
                f"""def func(self, db{params}):
                return self._do{_name.capitalize()}(db{_args})"""
            )
            setattr(cls, _name.lower(), locals().get("func"))

    if sql:
        ChildResource.createFunction("post")
        ChildResource.createFunction("put")
        ChildResource.createFunction("patch")
    else:
        ChildResource.createFunction(
            "post",
            *[f["name"] for f in fields if f["name"] != ChildResource.key],
            **{ChildResource.key: None},
        )
        ChildResource.createFunction("put", *[f["name"] for f in fields])
        ChildResource.createFunction(
            "patch",
            ChildResource.key,
            **{
                f["name"]: PatchData.UNCHANGED
                for f in fields
                if f["name"] != ChildResource.key
            },
        )
    return ChildResource
