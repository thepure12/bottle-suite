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
for the `[resources.<table>.roles]` sections gating writes. Auto-CRUD also
follows foreign keys at request time (`?levels=`, and a generic nested-ref
route) - see the FK-following examples under "Try it" below.

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
curl localhost:8080/health                       # custom resource, default path (no [resources.health] entry)

curl localhost:8080/tasks/1                      # auto-CRUD, get by primary key
curl localhost:8080/tasks?priority=high          # auto-CRUD, filter by query param (LIKE match)
curl 'localhost:8080/tasks/1?levels=2'           # auto-CRUD, follows the project_id FK, inlines it as "project"
curl localhost:8080/tags/1/task_tags             # auto-CRUD, generic nested-ref route (unshadowed by any hand-written resource)

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

Three hand-written `Resource` subclasses live here, not auto-generated -
`project_tasks.py`/`project_summary.py` for the two things a single-table
auto-CRUD route genuinely can't do, plus `health.py` to show what happens
when a custom resource has no matching config in `bottle_suite.toml`:

- **Multi-table joins** (`project_tasks.py`) - auto-CRUD's nested-ref/
  `?levels=` FK-following (see "Try it" above) only follows one
  relationship at a time. This response flattens three tables
  (`tasks -> task_tags -> tags`) into one row per task with a concatenated
  tag list, which is beyond a single FK hop - a plain SQL join in a custom
  resource is the correct fix for that, on sqlite or MySQL alike.
- **Computed/aggregate responses** (`project_summary.py`) - counts and
  sums have no auto-CRUD equivalent at all.
- **Default path fallback** (`health.py`) - it has no `[resources.health]`
  section in `bottle_suite.toml` at all, unlike the two resources above
  (which configure a custom `paths = [...]`). With no config to look up,
  `BottleSuite` falls back to `/<module_name>`, i.e. `/health`.
