# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Bottle Suite is a Python package (`bottle_suite`) that bundles several `bottle.py` plugins — CORS, REST resources, JWT auth, and SQL/SQLite — into a single `Bottle` subclass (`BottleSuite`), plus a CLI to scaffold and run projects, and an optional Vue/Nuxt admin dashboard.

The package vendors these small single-module `bottle.py` plugins directly under `src/bottle_suite/plugins/` (originally standalone PyPI packages by the same author, now maintained in-repo, re-exported via `plugins/__init__.py`):
- `plugins/rest.py` — provides `API` (the REST plugin, `self.rest`) and the `Resource` base class
- `plugins/jwt.py` — provides `JWTPlugin` (`self.jwt`) and `authFunc`
- `plugins/sql.py` — provides `sqlitePlugin`/`sqlPlugin` (`self.sqlite`/`self.sql`)
- `plugins/cors.py` — provides `CorsPlugin` (`self.cors`)

## Commands

Install for local dev (editable):
```bash
python3 -m pip install -e .
```

Run tests (unittest, run from repo root — every test module starts with `import _paths` to idempotently `os.chdir` into `tests/`, so discovery order doesn't matter):
```bash
python3 -m pip install -e ".[test]"     # adds coverage + webtest as test deps
python3 -m unittest discover -s tests -v
python3 -m unittest tests.test_bottle_suite -v
python3 -m unittest tests.test_bottle_suite.TestBottleSuite.test_genResoursesForDB -v
make test                                # = coverage run -m unittest discover -s tests -v && coverage report -m
```
Tests require `webtest`, `toml`, `PyJWT`, `pymysql`; the sqlite path is exercised for real against `tests/resources.db`/`tests/bottle_suite.toml`, while MySQL-only branches (no live MySQL server assumed) are exercised by mocking `pymysql.connect` via `tests/mysql_mock.py`. `[tool.coverage]` in `pyproject.toml` scopes measurement to the core package (`bottle_suite.py`, `resource_factory.py`, `resources.py`, `plugins/*.py`, `dashboard/resources/token.py` — excludes `src/scripts/` and the Nuxt client) with `fail_under = 100`; the suite currently holds 100% branch coverage there. See "Testing" under Architecture for suite structure and fixture-isolation gotchas.

Build/publish to Test PyPI (`Makefile`):
```bash
make dashboard       # npm install + npm run generate (builds src/bottle_suite/dashboard/dist)
make test-publish    # depends on `dashboard`; rm dist/build, python3 -m build, upload to testpypi
make test-upload     # upload existing dist/ to testpypi
```

Run the example app:
```bash
cd example && python3 app.py
```

Run the CLI locally without installing the console-script entry points:
```bash
python3 -m src.scripts.app -d -r --sqlite
python3 -m src.scripts.create
```
The `-d` flag serves the dashboard from `src/bottle_suite/dashboard/dist`, which does not exist until you run `make dashboard` (or `npm run generate` in `client/`) at least once — it is not committed to git (see below) and `setupDashboard` prints a warning at startup if it's missing.

`src/scripts/app.py` currently has no `if __name__ == "__main__": main()` guard, so `python3 -m src.scripts.app ...` silently does nothing (imports the module, defines `main`, exits 0) — only the installed `bottle-suite` console-script entry point (from `pyproject.toml`) actually calls `main()`. To run it locally without installing, invoke the function directly, e.g. `python3 -c "import sys; sys.argv=['app.py','-d','--sqlite']; from src.scripts.app import main; main()"`.

Dashboard client (Nuxt 3/4 + Nuxt UI v4, in `client/`): its build output (`npm run generate`) is generated directly into `src/bottle_suite/dashboard/dist` (see `nitro.output.publicDir` in `client/nuxt.config.ts`) and packaged via `MANIFEST.in`'s `graft src/bottle_suite/dashboard/dist`. That directory is intentionally gitignored/not committed — `make dashboard` (or `make test-publish`, which depends on it) builds it fresh instead. The Nuxt CLI needs Node >=20.12 (`node:util`'s `styleText`) and `nuxt typecheck` needs `vue-tsc` as a devDependency — both gaps surface as opaque errors if either is missing/too old.
```bash
cd client && npm install
npm run dev        # nuxt dev server
npm run generate   # static build -> writes directly into src/bottle_suite/dashboard/dist
```

## Architecture

### Core class: `BottleSuite` (`src/bottle_suite/bottle_suite.py`)

`BottleSuite` extends `bottle.Bottle`. Its `__init__` wires everything together in order, with each feature independently toggleable and configurable via constructor args OR `bottle_suite.toml` (toml values override constructor args — see `setup*` methods reading `self.cfg`):
1. `setupCors` — installs `CorsPlugin`
2. `setupSql` / `setupSqlite` — mutually exclusive (raises if both passed); installs `sqlPlugin`/`sqlitePlugin`, available to resources as an injected `db` cursor
3. `setupJwt` — installs `JWTPlugin`; auto-registers `GET/POST/OPTIONS /token` and `/users/current`
4. `setupDashboard` — serves the built Nuxt SPA from `dashboard/dist` at `/dashboard`, and overrides the JWT token endpoint with `DashboardToken.authenticate` if no custom auth func was set
5. `setupRest` — installs the vendored `API` plugin (`plugins/rest.py`), auto-imports any `Resource` subclasses found in `./resources/*.py` (via `importResourcesFromFile`, using `importlib`), and always registers three built-in meta-resources: `AllResources` (`/_resources`), `DataTypes` (`/_datatypes`), `Config` (`/bottle_suite_cfg`)
6. `createResForDB` (if `gen_db` and a DB is configured) — introspects every table in the connected database and auto-generates a CRUD `Resource` for each one that doesn't already have a route

Config precedence: `bottle_suite.toml` sections (`cors`, `rest`, `jwt`, `sqlite`, `sql`, `dashboard`, `resources.<name>.paths`, `resources.<name>.roles`) are read in `__init__`/`setRoles`/`importResourcesFromFile` and take precedence over the values passed into the constructor.

### Auto-generated DB resources: `resource_factory.py`

`createResource(name, fields, sql)` dynamically builds a `Resource` subclass per DB table:
- `key` = the column flagged as primary key in the introspected field list. `createResForDB` skips (with a printed message) any table where no field has `key == 1` before calling `createResource` — a table without a detected PK crashes `createResource` itself (its generated `post`/`patch` functions reference `ChildResource.key` unconditionally), so this guard is required; `getDBTables()`'s sqlite listing query already excludes PK-less tables via `sql LIKE '%PRIMARY%'`, but the MySQL listing query does not, which is why the guard lives in `createResForDB` rather than relying on introspection alone.
- `get` supports filtering by any query param (`LIKE`), a single-row lookup by primary key, a `levels` param for following foreign keys N levels deep via `getRefs` (which discovers FK relationships and recursively inlines referenced rows), and nested-resource routes like `/<ref_table>/<ref_id>/<table>`. `getRefs` branches on `bind_char` for FK discovery: MySQL uses `information_schema` (`FOREIGN_KEY_SQL`), sqlite uses `PRAGMA foreign_key_list(table)` — both paths normalize into the same 4-key dict shape. One known limitation remains: the nested-route branch in `get()` matches an FK by referenced-table name only, so a table with more than one FK to the same referenced table (e.g. a self-referencing `predator`/`prey` pair both pointing at `animals`) is ambiguous — it always resolves to whichever FK is discovered first, which may not be the column the caller meant.
- `post`/`put`/`patch` handlers are generated at class-creation time via `createFunction`, which builds a function via `exec()` with a parameter list matching the table's actual columns (so each resource's method signature reflects its schema) and dispatches to `_doPost`/`_doPut`/`_doPatch`. The route `createResForDB` registers for `put`/`patch` is `/<table>/<key>` — a URL param literally named `key` — while the table's real primary-key column can have any name (e.g. `id`); `createFunction` takes a `key_param` argument that renames that one positional arg to `key` in the generated outer signature (matching the route and satisfying the `API` plugin's required-field check) while still passing it through to `_doPost`/`_doPut`/`_doPatch` under the real column name, mirroring how `get`/`delete` already hardcode their own parameter as literally `key` and translate internally via `self.key`. `_doPut`/`delete` perform a real full-replace update / row delete (same try/except-then-500 shape as `_doPatch`).
- `bind_char` is `%s` for MySQL (`pymysql`) vs `?` for SQLite — the same code paths otherwise handle both DB backends. `getDBCursor`/`getDBTables` in `bottle_suite.py` pick the backend via `if self.sqlite: ... elif self.sql: ... else: raise` (not duck-typing/`try-except` — a bare except there used to silently mask a "neither configured" misuse as a MySQL connection attempt).

### Meta/admin resources: `resources.py`
`AllResources`, `DataTypes`, `Config` back the dashboard UI — they let the dashboard list tables, create tables (`POST /_resources`), and patch a resource's `roles`/`paths`/`fields` (schema alterations), which round-trip through `BottleSuite.alterDBTable`/`updateRoles`/`updatePaths`/`saveConfig`.

### OpenAPI spec generation: `openapi.py`
Builds a full OpenAPI 3.0.3 spec at runtime by walking `app.routes` — inferring path params, DB-table request/response schemas via introspection, marking `security` requirements on JWT-protected routes, and grouping routes into `tags`. Served for the dashboard's interactive API docs UI (see the `client/` section below).

### Testing (`tests/`)
`unittest`-based, one file per plugin/module: `test_bottle_suite.py` (core `BottleSuite`, config precedence, DB introspection/DDL), `test_resource_factory.py`, `test_resources.py`, `test_rest.py`, `test_jwt.py`, `test_sql.py`, `test_cors.py`, `test_dashboard_token.py`, `test_openapi.py`, `test_resource_scaffold.py`. Shared helpers:
- `_paths.py` — idempotent `os.chdir` into `tests/`, imported (`import _paths  # noqa: F401`) at the top of every test module instead of a single hardcoded `os.chdir("tests")` at import time.
- `mysql_mock.py` — `make_mysql_cursor()`/`patch_pymysql_connect()` build a `MagicMock(spec=pymysql.cursors.DictCursor)` (the `spec=` is required — `bottle_suite.getDBTables()` does `isinstance(db, pymysql.cursors.Cursor)` with no fallback branch) whose `execute()` returns an int by default, matching real pymysql/DBAPI rowcount semantics (unlike `sqlite3.Cursor.execute()`, which returns `self`) — this is what's needed to exercise `resource_factory.py`'s MySQL-only fallback branches (`except: rows = db.fetchall()`, `except AttributeError: last_row_id = db.lastrowid`).
- `db_fixtures.py` — `temp_sqlite_copy()` copies the committed `tests/resources.db` to a throwaway tempfile for any test that mutates rows/schema. **`temp_cfg_copy()` (copies `bottle_suite.toml` verbatim) is NOT sufficient isolation on its own for DB-mutating tests** — the committed toml sets `sqlite = "resources.db"`, and toml values always override constructor args, so a `BottleSuite(cfg_file=<copied toml>, sqlite=<tmp_db>, ...)` still silently operates on the real shared fixture (this bit a test during development and corrupted the committed fixture until caught via `git diff`/`git checkout`). Use `temp_cfg_pointing_at(tmp_db_path)` instead for any test that both mutates the DB and needs a writable cfg file (e.g. exercises `saveConfig`/`updateRoles`/`updatePaths`).
- `NONEXISTENT_CFG`-style sentinel filenames (a `cfg_file` that doesn't exist) are used throughout to force `self.cfg = {}` and let constructor args take full effect, bypassing `bottle_suite.toml`'s override — the standard pattern for testing non-default `cors`/`rest`/`jwt`/`sqlite`/`sql`/`dashboard` configurations.

After any test run, verify `tests/resources.db` is still the committed version (`git status --short tests/resources.db`) — even read-only sqlite3 connections can touch a few internal bookkeeping bytes without changing row/schema content (harmless, but `git diff --stat` will show a nonzero byte diff; `git checkout -- tests/resources.db` restores it).

### Live reload: `reload.py`
A near-empty module (`# Used to force reload`) that `BottleSuite.reloadServer()` rewrites to touch its mtime — this is the mechanism that triggers bottle's `reloader=True` process restart after the dashboard changes config/schema at runtime.

### CLI scripts (`src/scripts/`)
- `app.py` — the `bottle-suite` entry point; parses CLI flags (`--dir`, `--jwt`, `--sqlite`, `--dbhost/--dbname/--dbuser/--dbpass`, `--cors`, `-r`, `-d`), chdir's into `--dir` first (if given) so `bottle_suite.toml`/`resources/` resolve relative to it rather than the invoking shell's cwd, builds `BottleSuite(**kwargs)`, retries on `Exception` with a 5s backoff (but exits on `sqlite3.OperationalError`/`pymysql.err.OperationalError`), and cleans up the temp SQLite file on exit if `--sqlite` was used with no path.
- `create.py` — the `bottle-suite-create` entry point; interactively scaffolds a new project directory (`resources/` subfolder + `bottle_suite.toml`, copying `hello_world.py` as a starter resource), optionally creating a SQLite DB file or prompting for SQL connection details.
- `bottle-suite-resource` — the entry point for `resource()` in `create.py`: prompts for a resource name, validates it against `resource_scaffold.NAME_RE` (lowercase snake_case), writes `resources/<name>.py` from the `resource_scaffold.render()` template, and appends a default `[resources.<name>]` section (with `paths = ["/<name>", "/<name>/<key>"]`) to the project's `bottle_suite.toml`.

### User-facing resource convention
A user project defines `Resource` subclasses (from the internal `bottle_suite.plugins.rest` module, re-exported as `bottle_suite.Resource`) in a top-level `resources/` folder; `BottleSuite` scans that folder automatically unless `gen_res=False`. Each resource implements `options/get/post/put/patch/delete`; the vendored `API` plugin handles dispatch and injects `db` when a SQL/SQLite plugin is installed.

### Dashboard client (`client/`)
Nuxt 3/4 SPA (`ssr: false`, statically `nuxt generate`d and served by `BottleSuite` itself — no Node/Nitro server at runtime) using Nuxt UI v4 + Tailwind v4. Uses Nuxt 4's `app/`-as-srcDir layout: pages/components/composables/layouts/middleware all live under `client/app/`, and **`app.config.ts` must live at `client/app/app.config.ts`, not the project root** — Nuxt resolves it relative to the app srcDir, and a root-level copy is silently ignored (no error, it just falls back to defaults). `@nuxtjs/auth-next`/`@nuxtjs/axios` (unmaintained on Nuxt 3/4) are replaced by hand-rolled composables in `client/app/composables/`: `useAuth.ts` (JWT in a reactive cookie, against `BottleSuite`'s `/token` endpoint), `useApi.ts` (shared `$fetch.create` instance, attaches the bearer token, logs out only on 401 — not 400, since `PUT /bottle_suite_cfg` legitimately 400s on bad TOML), `useConfigStore.ts` (TOML round-trip via `smol-toml`), `useResourcesStore.ts`, `useToastError.ts`. Pages under `client/app/pages/` (`config.vue`, `resources/index.vue`, `resources/[id].vue`, `login.vue`, `index.vue`, `setup.vue`, `python-resources/index.vue`, `python-resources/[name].vue`) map directly to the `_resources`/`bottle_suite_cfg` meta-endpoints above (the `python-resources` pages list/inspect the hand-authored `Resource` subclasses in a project's `resources/` folder, as opposed to the auto-generated DB resources under `resources/`). `api-explorer.vue` renders the spec served by `openapi.py` via a hand-rolled Nuxt module under `client/modules/`: `nuxt-swagger-ui` (global client-only `<SwaggerUIViewer>` component), which wraps the third-party Swagger UI library. Custom brand colors and fonts live in `client/app/assets/css/main.css`: Tailwind v4's `@theme` block tree-shakes any custom token not referenced by a literal utility class in a template, so colors only ever consumed via `var(...)` at runtime (as Nuxt UI's `ui.colors` aliases in `app.config.ts` do) must go in `@theme static` instead, or they silently vanish from the compiled CSS. It's a separate npm project — not part of the Python package's dependency/test chain, only its build output is bundled into the wheel.

`client/nuxt.config.ts` sets `components: [{ path: '~/components', pathPrefix: false }]` — every template in this app references subdirectory components by their bare filename (`<ResourceDataTable>`, `<PageHeader>`, ...) rather than Nuxt's default directory-prefixed name (`ResourcesResourceDataTable`, `BasePageHeader`, ...). Without `pathPrefix: false`, any component whose filename doesn't start with its parent directory's PascalCase name silently fails to resolve at runtime (no build error) — this is what broke the resource-detail page (`ResourceDataTable`/`ResourceEditDialog` under `components/resources/`) before the fix. Keep new subdirectory components' bare filenames unique across the whole `components/` tree, since prefixing is now off globally.

`client/app/components/base/` holds shared UI primitives reused across pages: `PageHeader` (title/description + `#actions` slot), `EmptyState` (icon/message + `#action` slot), `StatCard`, `BrandMark` (the dot+wordmark, `size="sm"|"lg"`), `BrandScreen` (full-viewport shell wrapping `BrandMark` — used by `login.vue`/`error.vue`), and `LoadingRows` (skeleton placeholders, `variant="list"|"stat"|"card"`) in place of plain "Loading..." text. `client/app/utils/humanize.ts` exports `humanizeKey()` for turning raw DB/pragma keys (`dflt_value`, `notnull`, `cid`, ...) into readable labels in `ResourceEditDialog`/`ResourceDataTable`.

`client/app/layouts/default.vue` renders a `UBreadcrumb` in the navbar's `#title` slot (driven by each page's `definePageMeta({ title: '...' })`, with a "DB Resources" segment prepended for `/resources/[id]` routes) instead of a static title, and mounts a `UDashboardSearch`/`UDashboardSearchButton` Cmd/Ctrl+K command palette seeded from the sidebar nav items plus `useResourcesStore()`'s resource list.
