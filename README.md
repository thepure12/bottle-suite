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