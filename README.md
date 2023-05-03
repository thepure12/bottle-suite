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