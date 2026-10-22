"""Found automatically at the project root. configure(app) runs after
Bottler has registered every route, so it can add or override anything."""
import time

from bottle import request, response


def configure(app):
    # A plain Bottle route outside api_prefix and outside default_roles.
    @app.route("/healthz")
    def healthz():
        return {"status": "ok"}

    # Bottle hooks work as usual.
    @app.hook("before_request")
    def startTimer():
        request.environ["started"] = time.perf_counter()

    @app.hook("after_request")
    def addTiming():
        started = request.environ.get("started")
        if started is not None:
            elapsed = (time.perf_counter() - started) * 1000
            response.set_header("X-Response-Time", f"{elapsed:.1f}ms")
