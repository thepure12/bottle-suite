# Plugins on a plain Bottle app

`bottler.plugins` holds the REST, JWT, SQL and CORS plugins that `Bottler`
is built from. They also work on their own, on a plain `bottle.Bottle`.
Use this when you want one or two of them without Bottler's config file,
resource folder scan or dashboard.

## Run it

```bash
cd examples/plain_bottle
python3 app.py
```

`app.py` creates `books.db` on first run.

## Try it

```bash
curl localhost:8080/books
curl localhost:8080/books/1

TOKEN=$(curl -s -X POST localhost:8080/token -H 'Content-Type: application/json' \
  -d '{"username": "demo", "password": "demo-pw"}' |
  python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')

curl -X POST localhost:8080/books -H 'Content-Type: application/json' \
  -d '{"title": "Ulysses"}'                       # 400, no token
curl -X POST localhost:8080/books -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"title": "Ulysses"}'   # 201
```

## Plugins used

| Plugin | What it does |
|---|---|
| `API` + `Resource` | Maps `get`/`post`/... methods to routes and fills arguments from the URL and JSON body |
| `sqlitePlugin` (or `sqlPlugin` for MySQL) | Opens a connection per request and passes a `db` cursor |
| `JWTPlugin` | Issues tokens on the token path and checks `roles` route config |
| `CorsPlugin` | Adds CORS headers; pass `origins=[...]` to allowlist |
