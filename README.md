# Bottle Suite
Bottle.py suite with CORS, SQL, REST, and JWT

## Installation

```bash
python3 -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ bottle-suite --upgrade
```

## Usage
### CLI

#### Create Project
```bash
$ bottle-suite-create
Enter project name. <bottle-suite-project>:
Create a SQLite database? [y/N]:
Attach an SQL database? [y/N]:
Created project bottle-suite-project
    cd bottle-suite-project
    bottle-suite -d -r
```

#### Run
```bash
$ cd bottle-suite-project
$ bottle-suite -d -r
View dashboard @ http://localhost:8000/dashboard
Bottle v0.13-dev server starting up (using WSGIRefServer(dashboard=True))...
Listening on http://localhost:8000/
Hit Ctrl-C to quit.
```

#### Options
```
usage: bottle-suite [-h] [--port PORT] [--host HOST] [--jwt JWT_KEY] [--sqlite [PATH]] [--dbhost DBHOST] [--dbname DBNAME] [--dbuser DBUSER] [--dbpass DBPASS] [--cors CORS] [-r] [-d]

optional arguments:
  -h, --help       show this help message and exit
  --port PORT      Port to listen on
  --host HOST      Host to listen on
  --jwt JWT_KEY    JWT key
  --sqlite [PATH]  Path to SQLite database (default: bottle-suite/src/scripts/tmp.db)
  --dbhost DBHOST  SQL database host
  --dbname DBNAME  SQL database name
  --dbuser DBUSER  SQL database username
  --dbpass DBPASS  SQL database password
  --cors CORS      Enable CORS
  -r               Automatic reloading
  -d               Enable dashboard
```

### Import
app.py
```python
from bottle_suite import BottleSuite

app = BottleSuite()
app.run(reloader=True)
```

## Resources
### Resource Folder
Bottle Suite will attempt to automatically find Resources objects in a resource folder in the working directory and create endpoints for them. By default it will look for a folder named "resources". All ".py" files in the folder will be scanned for Resource objects.

#### Example Project Structure
```
├── src
│   ├── resources
│   │   ├── __init__.py
│   │   ├── resource_a.py
|   |   ├── resource_b.py
│   ├── app.py
```

### Resource Objects
See [Bottle REST Tutorial](https://github.com/thepure12/bottle-rest/blob/main/docs/tutorial.rst)

#### resource_a.py
```python
from bottle_suite import Resource

class ResourceA(Resource):

    def options(self):
        pass

    def get(self):
        return {}
    
    def post(self):
        pass
    
    def put(self):
        pass

    def patch(self):
        pass

    def delete(self):
        pass
```

### Adding Endpoints for Resources
Bottle Suite has a Bottle REST object. Resources can be added by accessing the Bottle REST object and calling ***addResource()***.

#### app.py
```python
from resources.resource_a import ResourceA
from bottle_suite import BottleSuite

app = BottleSuite()
app.rest.addResource(ResourceA, "/resource_a")
app.run(reloader=True)
```

### Auto-Generated Database Resources
When a SQLite or SQL database is configured (`sqlite=...` / `sql=...`, via
the constructor or `bottle_suite.toml`), `BottleSuite` introspects every
table on startup and auto-generates a full CRUD `Resource` for each table
that doesn't already have a route (`gen_db=True` by default - pass
`gen_db=False` to disable). Only tables with a detected primary key are
eligible.

For a table `widgets` with primary key `id`, this registers:
- `GET/POST /widgets` - list (filterable by any `?column=value`, LIKE-matched) / create
- `GET/PUT/PATCH/DELETE /widgets/<id>` - fetch/replace/patch/delete a single row
- `GET /<ref_table>/<ref_id>/widgets` - fetch rows referencing another table's row via a detected foreign key

Any auto-CRUD `GET` also accepts `?levels=N` to inline foreign-key
references N levels deep - e.g. `GET /widgets/1?levels=2` replaces a
`category_id` column with a nested `category` object.

Per-table role gating and custom paths are configured under
`[resources.<table>]` in `bottle_suite.toml`. See `example/` for a full
working demo (`example/bottle_suite.toml`, `example/README.md`).

### API Prefix
Set `api_prefix` (constructor kwarg or top-level `bottle_suite.toml` key,
e.g. `api_prefix = "/api"`) to prepend a fixed prefix to every route
BottleSuite registers as part of your project's own API — hand-authored
resources, auto-generated database resources, and the JWT `/token`/
`/users/current` endpoints. This is useful when something else (a
static-site resource, a frontend build) needs to own the unprefixed
paths. Bottle Suite's own dashboard and meta/admin routes (`/dashboard`,
`/openapi.json`, `/_resources`, etc.) are never affected by `api_prefix`.

An individual `Resource` subclass can opt out of the global prefix (or use
a different one) by setting its own `api_prefix` class attribute:

```python
from bottle_suite import Resource

class ResourceA(Resource):
    api_prefix = ""  # always unprefixed, even if the app sets api_prefix

    def get(self):
        return {}
```

A resource with an `api_prefix` override — e.g. a root-mounted catch-all like `/<path:path>` serving a
static SPA build — is always registered *after* every default-prefixed route (hand-authored, built-in,
and auto-generated DB resources), so it can never shadow a real API route no matter what order its
module happens to load in.

### Default Roles
Hand-authored and auto-generated database resources are open unless they
set `roles`. Set `default_roles` (constructor kwarg or top-level
`bottle_suite.toml` key) to protect all of them at once:

```toml
default_roles = true                  # any valid token
# default_roles = ["admin", "finance"]  # token must hold at least one role
```

A list can also be given as a comma-separated string (`"admin,finance"`).
The default applies only to methods that declare no roles of their own.
Roles set on the resource class, or under `[resources.<name>.roles]`, win.
An explicit `false` opts a method out, for example a public static-site
resource:

```toml
[resources.spa.roles]
get = false
```

`OPTIONS` never gets the default, so CORS preflight still works. The
built-in meta routes (`/_resources`, `/_roles`, ...) keep their own
`roles = true` and ignore `default_roles`. The JWT `/token` route is
unaffected.

### Mounting Packages
One app can serve several installed packages, each under its own URL prefix
and each with its own database. List them under `mounts` in
`bottle_suite.toml`:

```toml
jwt = "..."
api_prefix = "api"

[mounts]
trax = "trax_connector"        # short form: config folder = "trax"

[mounts.bri]
package = "bri_connector"      # importable package with a resources/ subpackage
base_dir = "connectors/bri"    # its config folder (default: the mount name)
```

Each mount is a child `BottleSuite` built from `<package>.resources` (not
`./resources`), served at `<api_prefix>/<name>/`. Its own
`<base_dir>/bottle_suite.toml` sets its `sql`/`sqlite`, `resources.*` paths
and roles, and `default_roles`; DB auto-CRUD works per mount. The child always
takes `jwt`, `cors`, `rest`, `dashboard`, `openapi` and `api_prefix` from the
parent (its own values for those are ignored), so one token works everywhere
and only the parent's `/token` issues one. A mount without its own
`default_roles` inherits the parent's.

The package's `__init__.py` may define `configure(app)`. It runs last, like
`hooks.py`, and `app.base_dir` is the mount's config folder. Packages never
get an `auth.py` or `hooks.py` from the working directory.

A package can also run on its own (e.g. in its own repo for development):
`BottleSuite(package="bri_connector", base_dir="config")`.

### Custom Setup Hooks
If a project defines a top-level `hooks.py` with a callable `configure(app)`,
`BottleSuite` calls it automatically at the very end of `__init__` — after
every resource, DB table, and built-in route (including `/openapi.json`) is
already registered. This is the place to add anything `BottleSuite` doesn't
already cover: extra routes, additional Bottle plugins, middleware, or
overriding a route `BottleSuite` itself just set up.

#### hooks.py
```python
def configure(app):
    @app.route("/healthz")
    def healthz():
        return {"status": "ok"}
```

Disable auto-discovery with `gen_hooks=False` (constructor-only, not
`bottle_suite.toml`-configurable). This works the same way whether the app
is started via the `bottle-suite` CLI, a hand-rolled `app.py`, or a WSGI
deploy — `hooks.py` just needs to sit at the process's working directory
when `BottleSuite()` is constructed.