"""Builds an OpenAPI 3.0 spec by walking the routes/resources BottleSuite has
already registered at runtime -- no separate spec is maintained by hand, so
the documented API surface can never drift from what is actually running."""
from __future__ import annotations
import re
import inspect
from importlib.metadata import version as _pkg_version, PackageNotFoundError
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover -- never True at runtime
    from .bottle_suite import BottleSuite

PATH_PARAM_RE = re.compile(r"<(\w+)(?::[^>]*)?>")
EXCLUDED_PREFIXES = (
    "/dashboard",
    "/openapi.json",
    "/_resources",
    "/_datatypes",
    "/bottle_suite_cfg",
    "/_python_resources",
)
AUTH_RULES = {"/token", "/users/current"}

DEFAULT_SCHEMA = {"type": "string"}
SQL_TYPE_MAP = {
    "INT": {"type": "integer"},
    "INTEGER": {"type": "integer"},
    "TINYINT": {"type": "integer"},
    "SMALLINT": {"type": "integer"},
    "MEDIUMINT": {"type": "integer"},
    "BIGINT": {"type": "integer"},
    "INT2": {"type": "integer"},
    "INT8": {"type": "integer"},
    "REAL": {"type": "number", "format": "float"},
    "DOUBLE": {"type": "number", "format": "double"},
    "FLOAT": {"type": "number", "format": "float"},
    "NUMERIC": {"type": "number"},
    "DECIMAL": {"type": "number"},
    "BOOLEAN": {"type": "boolean"},
    "BOOL": {"type": "boolean"},
    "DATE": {"type": "string", "format": "date"},
    "DATETIME": {"type": "string", "format": "date-time"},
    "TIMESTAMP": {"type": "string", "format": "date-time"},
    "TEXT": {"type": "string"},
    "CHAR": {"type": "string"},
    "VARCHAR": {"type": "string"},
    "CLOB": {"type": "string"},
    "BLOB": {"type": "string", "format": "binary"},
}


def _mapSqlType(sql_type) -> dict:
    base = re.split(r"[\s(]", (sql_type or "").strip().upper(), 1)[0]
    return dict(SQL_TYPE_MAP.get(base, DEFAULT_SCHEMA))


def _isExcluded(rule: str) -> bool:
    return rule.startswith(EXCLUDED_PREFIXES)


def _pathParams(rule: str) -> list:
    return [
        {"name": name, "in": "path", "required": True, "schema": {"type": "string"}}
        for name in PATH_PARAM_RE.findall(rule)
    ]


def _operationId(method: str, rule: str) -> str:
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", rule).strip("_")
    return f"{method.lower()}_{slug}"


def _tag(resource, rule: str) -> str:
    if rule in AUTH_RULES:
        return "Auth"
    if resource is not None:
        return resource.name
    return "default"


def _tableSchemaRef(schemas: dict, resource, fields: list) -> str:
    name = resource.name
    if name not in schemas:
        properties = {}
        required = []
        for f in fields:
            properties[f["name"]] = _mapSqlType(f.get("type"))
            if f.get("notnull") and not f.get("default") and not f.get("key"):
                required.append(f["name"])
        schema = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        schemas[name] = schema
    return name


def _paramSchema(callback, skip: set) -> dict:
    properties = {}
    required = []
    for pname, param in inspect.signature(callback).parameters.items():
        if pname in skip or param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        properties[pname] = dict(DEFAULT_SCHEMA)
        if param.default is inspect.Parameter.empty:
            required.append(pname)
    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _dbOperation(method: str, resource, fields: list, schemas: dict, has_key: bool) -> dict:
    schema_name = _tableSchemaRef(schemas, resource, fields)
    ref = {"$ref": f"#/components/schemas/{schema_name}"}
    operation = {"responses": {}}
    if method == "GET":
        schema = (
            ref
            if has_key
            else {
                "type": "object",
                "properties": {resource.table: {"type": "array", "items": ref}},
            }
        )
        operation["responses"]["200"] = {
            "description": "Successful response",
            "content": {"application/json": {"schema": schema}},
        }
    elif method == "DELETE":
        operation["responses"]["200"] = {"description": "Successful response"}
    else:
        body_schema = ref
        if method == "PATCH":
            body_schema = {
                k: v for k, v in schemas[schema_name].items() if k != "required"
            }
        operation["requestBody"] = {
            "required": True,
            "content": {"application/json": {"schema": body_schema}},
        }
        status = "201" if method == "POST" else "200"
        operation["responses"][status] = {
            "description": "Successful response",
            "content": {"application/json": {"schema": ref}},
        }
    return operation


def _plainOperation(method: str, callback, skip: set) -> dict:
    operation = {"responses": {"200": {"description": "Successful response"}}}
    if method in ("POST", "PUT", "PATCH"):
        body = _paramSchema(callback, skip)
        if body["properties"]:
            operation["requestBody"] = {
                "content": {"application/json": {"schema": body}}
            }
    return operation


def _infoBlock(app: "BottleSuite") -> dict:
    raw = app.cfg.get("openapi", {})
    cfg = raw if isinstance(raw, dict) else {}
    try:
        pkg_version = _pkg_version("bottle_suite")
    except PackageNotFoundError:
        pkg_version = "0.0.0"
    return {
        "title": cfg.get("title", "Bottle Suite API"),
        "version": cfg.get("version", pkg_version),
        "description": cfg.get(
            "description", "Auto-generated from the running BottleSuite app."
        ),
    }


def buildSpec(app: "BottleSuite") -> dict:
    db_tables = app.getDBTables() if (app.sql or app.sqlite) else {}
    schemas = {}
    paths = {}
    has_bearer = False
    for route in app.routes:
        rule = route.rule
        method = route.method
        if method == "OPTIONS" or _isExcluded(rule):
            continue
        resource = getattr(route.callback, "__self__", None)
        path_params = _pathParams(rule)
        path_param_names = {p["name"] for p in path_params}
        table = getattr(resource, "table", None)

        if table:
            operation = _dbOperation(
                method, resource, db_tables.get(table, []), schemas,
                "key" in path_param_names,
            )
        else:
            skip = {"db"} | path_param_names
            operation = _plainOperation(method, route.callback, skip)

        operation["tags"] = [_tag(resource, rule)]
        operation["operationId"] = _operationId(method, rule)
        if path_params:
            operation["parameters"] = path_params
        if route.config.get("roles") and getattr(app, "jwt", None):
            operation["security"] = [{"bearerAuth": []}]
            has_bearer = True

        paths.setdefault(rule, {})[method.lower()] = operation

    spec = {
        "openapi": "3.0.3",
        "info": _infoBlock(app),
        "servers": [{"url": "/"}],
        "paths": paths,
    }
    components = {}
    if schemas:
        components["schemas"] = schemas
    if has_bearer:
        components["securitySchemes"] = {
            "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        }
    if components:
        spec["components"] = components
    return spec
