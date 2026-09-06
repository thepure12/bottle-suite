# Bottle Suite example

A small task-tracker app demonstrating what `BottleSuite` gives you for free
(CORS, sqlite-backed auto-CRUD, JWT auth with per-route role gating, the
admin dashboard) plus when it's worth hand-writing a `Resource` instead.

## Schema

```
projects --< tasks >-- tags   (many-to-many via task_tags)
```

- `projects` - `id`, `name`, `description`, `archived`
- `tasks` - `id`, `project_id` (FK -> projects), `title`, `priority`, `done`, `due_date`
- `tags` - `id`, `name`
- `task_tags` - join table between `tasks` and `tags`

Every table has its own single-column `id` primary key (including the join
table), so all four get correct, auto-generated CRUD routes
(`/projects`, `/projects/<key>`, `/tasks`, ... ) - see `bottle_suite.toml`
for the `[resources.<table>.roles]` sections gating writes.

## Run it

```bash
cd example
python3 app.py
```

This starts on `http://localhost:8080`. The dashboard UI at `/dashboard`
needs a built client (`make dashboard` from the repo root, or `npm run
generate` in `client/`) - without it you'll see a "no build found" message
printed at startup, but every API route below still works fine over plain
HTTP/curl.

## Auth: two separate logins

The REST API and the dashboard UI authenticate independently, on purpose -
they're different consumers with different credentials:

- **`/token`** - the REST API's own login, backed by a hardcoded pair of
  demo users in `app.py` (`authenticate`). This is the pattern a real
  project would actually write: authenticate against your own users. A
  real project's `/token` is whatever this is - `BottleSuite` doesn't
  provide it.
- **`/dashboard/token`** - the dashboard UI's own login, backed by a single
  bootstrapped admin account. `BottleSuite` wires this up automatically
  whenever the dashboard is enabled, and it's excluded from `/openapi.json`
  and `/_resources` - it's internal to the dashboard, not part of the
  API surface a REST client should call.

### REST API login (`/token`)

Two demo accounts are hardcoded in `app.py`'s `USERS`/`authenticate` -
no setup step needed:

| username | password         | roles       |
|----------|------------------|-------------|
| `admin`  | `demo-admin-pw`  | `["admin"]` |
| `alice`  | `demo-alice-pw`  | `[]`        |

```bash
curl -X POST localhost:8080/token \
  -H 'Content-Type: application/json' \
  -d '{"username": "alice", "password": "demo-alice-pw"}'
# => {"token": "..."}
```

These passwords/hashes are demo-only placeholders, same as the `jwt` key
below - don't reuse this pattern verbatim for real credentials.

The `jwt` key in `bottle_suite.toml` is also a demo-only placeholder -
regenerate it (`python3 -c "import secrets; print(secrets.token_urlsafe(32))"`)
before reusing this config for anything beyond this local example.

### Dashboard UI login (`/dashboard/token`)

No dashboard username/password is committed to `bottle_suite.toml` on
purpose. The first time you open the dashboard, bootstrap your own admin
credentials:

```bash
curl -X POST localhost:8080/dashboard/setup \
  -H 'Content-Type: application/json' \
  -d '{"username": "admin", "password": "changeme"}'
```

(Or open `http://localhost:8080/dashboard` in a browser if you've built the
client - it walks you through the same setup wizard.) Then get a bearer
token for that account:

```bash
curl -X POST localhost:8080/dashboard/token \
  -H 'Content-Type: application/json' \
  -d '{"username": "admin", "password": "changeme"}'
# => {"token": "..."}
```

This token is only meaningful to the dashboard UI - it carries no `roles`
claim, so it won't pass the `["admin"]` checks below either. Use `/token`
above for the REST API.

## Try it

Reads are public, writes require a bearer token from `/token`, and deletes
require that token to carry the `admin` role:

```bash
curl localhost:8080/projects                    # auto-CRUD, public
curl localhost:8080/projects/1/tasks             # custom resource, joined with tags
curl localhost:8080/projects/1/summary           # custom resource, aggregate counts

curl -X POST localhost:8080/tasks \
  -H "Authorization: Bearer <alice's token>" \
  -H 'Content-Type: application/json' \
  -d '{"project_id": 1, "title": "Ship it", "priority": "high", "done": false, "due_date": "2026-09-30"}'
# => 201, alice doesn't need the admin role just to create a task

curl -X DELETE localhost:8080/tasks/1 \
  -H "Authorization: Bearer <alice's token>"
# => 403 ("You do not have permission to access this content") - alice
#    isn't an admin

curl -X DELETE localhost:8080/tasks/1 \
  -H "Authorization: Bearer <admin's token>"
# => 200 - admin's token carries the "admin" role
```

The same `POST /tasks` without the `Authorization` header gets a 400
("Authorization header is expected") - that's the `[resources.tasks.roles]`
config in `bottle_suite.toml` at work (note `get = false` there means "no
role required", i.e. public - the framework's roles are opt-in per method,
not a boolean "requires auth"). `delete = ["admin"]` goes a step further
than `post`/`put`/`patch`'s plain `true` ("any logged-in user"): it checks
the token's `roles` claim, so a valid token *without* the `admin` role gets
a 403 on `DELETE` even though it's accepted for writes.

## `resources/`

`project_tasks.py` and `project_summary.py` are hand-written `Resource`
subclasses, not auto-generated. Auto-CRUD only ever queries one table, so
they exist for the two cases it can't cover:

- **Cross-table joins** (`project_tasks.py`) - the framework does have a
  built-in nested-ref/`?levels=` FK-following feature for this, but it's
  implemented via a MySQL-only `information_schema` query, so it doesn't
  work against this sqlite-backed example. A plain SQL join in a custom
  resource is the correct fix on sqlite.
- **Computed/aggregate responses** (`project_summary.py`) - counts and
  sums have no auto-CRUD equivalent at all.
