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