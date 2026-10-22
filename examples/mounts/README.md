# Mounting packages

One process serves two packages, each with its own sqlite database, under
one JWT login:

```
/api/token               parent app (auth.py)
/api/billing/...         billing_api package,   billing/data.db
/api/inventory/...       inventory_api package, inventory/data.db
```

```
mounts/
├── app.py               creates both databases, then starts the parent
├── bottler.toml         jwt, api_prefix and [mounts]
├── auth.py              the only /token login
├── billing/             billing_api's config folder
│   ├── bottler.toml
│   └── schema.sql
├── billing_api/         a normal Python package with a resources/ subpackage
├── inventory/
│   ├── bottler.toml
│   └── schema.sql
└── inventory_api/
```

## Run it

```bash
cd examples/mounts
python3 app.py
```

## Try it

Demo users from `auth.py` (demo-only passwords):

| username | password       | roles         |
|----------|----------------|---------------|
| `fran`   | `demo-fran-pw` | `["finance"]` |
| `sam`    | `demo-sam-pw`  | `[]`          |

```bash
login() {
  curl -s -X POST localhost:8080/api/token -H 'Content-Type: application/json' \
    -d "{\"username\": \"$1\", \"password\": \"$2\"}" |
    python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])'
}
FRAN=$(login fran demo-fran-pw)
SAM=$(login sam demo-sam-pw)

# Inventory: auto-CRUD on its own database, reads are open.
curl localhost:8080/api/inventory/products
curl localhost:8080/api/inventory/products/low_stock     # threshold from inventory/bottler.toml
curl -X PATCH localhost:8080/api/inventory/products/2 \
  -H "Authorization: Bearer $SAM" -H 'Content-Type: application/json' \
  -d '{"quantity": 25}'                                  # any token may write

# Billing: default_roles = ["finance"] in billing/bottler.toml.
curl localhost:8080/api/billing/invoices -H "Authorization: Bearer $SAM"    # 403
curl localhost:8080/api/billing/invoices -H "Authorization: Bearer $FRAN"
curl localhost:8080/api/billing/invoices/totals -H "Authorization: Bearer $FRAN"
```

## What it shows

- Each mount is a child `Bottler` with its own `bottler.toml`, database,
  DB auto-CRUD and resources.
- The child takes `jwt`, `cors`, `api_prefix` and friends from the parent,
  so the one token from `/api/token` works on every mount.
- `default_roles` in a child applies only to that child.
- A package's `configure(app)` in `__init__.py` runs last and can read its
  own settings from `app.cfg`.
- The sqlite paths in the child configs are relative to the working
  directory, which is why `app.py` changes into this folder first.
