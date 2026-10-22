# Hello world

The smallest Bottler app: hand-written resources only, no database, no
JWT.

## Run it

```bash
cd examples/hello_world
python3 app.py
```

## Try it

```bash
curl localhost:8080/health                   # path from the module name
curl localhost:8080/greeting                 # {"message": "Hello, world!"}
curl localhost:8080/greeting/Ada             # URL parameter fills `name`
curl 'localhost:8080/greeting/Ada?shout=1'   # query string via self.params

curl -X POST localhost:8080/greeting \
  -H 'Content-Type: application/json' \
  -d '{"name": "Ada", "greeting": "Hi"}'
# => {"message": "Hi, Ada!"}

curl -X POST localhost:8080/greeting -H 'Content-Type: application/json' -d '{}'
# => 400 {"name": "This field is required"}
```

## What it shows

- `resources/health.py` has no config, so it is served at `/health`.
- `resources/greeting.py` gets its paths from `[resources.greeting]` in
  `bottler.toml`.
- Method arguments come from URL parameters and the JSON body. An argument
  without a default is required.
- `jwt = false` turns off the `/token` endpoint and the random-key
  warning.
