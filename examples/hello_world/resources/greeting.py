from bottler import Resource


class Greeting(Resource):
    # `name` comes from the URL (/greeting/<name>) when present. On
    # /greeting it falls back to the default.
    def get(self, name="world"):
        message = f"Hello, {name}!"
        # Query-string values are on self.params.
        if self.params.get("shout"):
            message = message.upper()
        return {"message": message}

    # `name` has no default, so a POST without it in the JSON body gets
    # 400 {"name": "This field is required"}.
    def post(self, name, greeting="Hello"):
        return {"message": f"{greeting}, {name}!"}
