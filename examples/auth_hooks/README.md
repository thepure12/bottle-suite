# Auth and hooks

A project with no `app.py`, run by the `bottler` CLI. It shows the
project-root conventions and the app-wide settings:

- `auth.py` - its `authenticate()` becomes the `/token` login.
- `hooks.py` - its `configure(app)` runs last and adds a plain route and
  Bottle hooks.
- `api_prefix = "/api"` - every API route, including `/token`, moves
  under `/api`.
- `default_roles = true` - every resource method needs a token unless it
  opts out.
- `[cors] origins` - CORS headers only for an allowlisted origin.

## Run it

```bash
bottler --dir examples/auth_hooks --port 8080
```

The same project also runs under a WSGI server:

```bash
gunicorn --chdir examples/auth_hooks bottler.wsgi:application
```

## Try it

Demo users from `auth.py` (demo-only passwords):

| username | password        | roles       |
|----------|-----------------|-------------|
| `admin`  | `demo-admin-pw` | `["admin"]` |
| `alice`  | `demo-alice-pw` | `[]`        |

```bash
curl localhost:8080/healthz                  # from hooks.py, no token
curl -i localhost:8080/api/notes             # public (get = false), has X-Response-Time

TOKEN=$(curl -s -X POST localhost:8080/api/token \
  -H 'Content-Type: application/json' \
  -d '{"username": "alice", "password": "demo-alice-pw"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')

curl localhost:8080/api/me                   # 400, no token (default_roles)
curl localhost:8080/api/me -H "Authorization: Bearer $TOKEN"

curl -X POST localhost:8080/api/notes \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"text": "Buy milk"}'                  # 201, author = alice

curl -X DELETE localhost:8080/api/notes/1 \
  -H "Authorization: Bearer $TOKEN"          # 403, alice is not an admin

curl -i localhost:8080/api/notes -H 'Origin: http://localhost:3000'
# Access-Control-Allow-Origin: http://localhost:3000
```

Log in as `admin` the same way to delete a note.
