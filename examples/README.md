# Examples

Each folder is a complete project. Run it from its own folder (see its
README).

| Example | Shows |
|---|---|
| [`hello_world`](hello_world) | Hand-written resources, URL and body arguments, path config. No database, no JWT. |
| [`task_tracker`](task_tracker) | sqlite auto-CRUD, foreign keys, per-method roles, custom joins and aggregates, the dashboard. |
| [`auth_hooks`](auth_hooks) | `auth.py` and `hooks.py` conventions, `api_prefix`, `default_roles`, CORS allowlist, running with the `bottler` CLI or WSGI. |
| [`mounts`](mounts) | Two packages with their own databases mounted into one app under one login. |
| [`plain_bottle`](plain_bottle) | The vendored plugins on a plain `bottle.Bottle`, without the `Bottler` class. |
