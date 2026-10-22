from bottler import Bottler

# Reads bottler.toml and imports every Resource in ./resources.
app = Bottler()
app.run(port=8080, reloader=True)
