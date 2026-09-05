# Vendored from bottle-rest (https://github.com/thepure12/bottle-rest), MIT License.
from enum import Enum
from typing import Type, Union
from bottle import PluginError, Route, Bottle, abort, request, response
from inspect import signature


class Resource(object):
    class Methods(Enum):
        GET = "GET"
        POST = "POST"
        PUT = "PUT"
        PATCH = "PATCH"
        DELETE = "DELETE"
        OPTIONS = "OPTIONS"

    _name = ""
    rules = []

    @property
    def params(self):
        return request.params

    @property
    def name(self):
        if self._name:
            return self._name
        else:
            return self.__class__.__name__

    @name.setter
    def name(self, value):
        self._name = value

    def getFunction(self, method: Methods):
        return getattr(self, method.value.lower(), None)

    @classmethod
    def getRouteConfig(cls, method: Methods) -> dict:
        return getattr(cls, method.value.upper(), {})

    @classmethod
    def setRouteConfig(cls, method: Methods, cfg: dict) -> None:
        setattr(cls, method.value.upper(), cfg)


class API(object):
    name = "bottle-rest"
    api = 2
    keyword = "bottle-rest"

    def __init__(self, debug=False):
        self.debug = debug
        self.resources = []

    def setup(self, app: Bottle):
        """Make sure that other installed plugins don't affect the same
        keyword argument."""
        self.app = app
        for other in app.plugins:
            if not isinstance(other, API):
                continue
            if other.keyword == self.keyword:
                raise PluginError(
                    "Found another sqlite plugin with "
                    "conflicting settings (non-unique keyword)."
                )

    def apply(self, callback, context: Route):
        def _wrapper(*args, **kwargs):
            params = signature(callback).parameters
            if self.debug:
                print(f"\033[96mbottle_rest:\033[0m path: {request.path}")
                print(f"\033[96mbottle_rest:\033[0m args: {args}")
                print(f"\033[96mbottle_rest:\033[0m kwargs: {kwargs}")
                print(
                    f"\033[96mbottle_rest:\033[0m url params: {list(request.params.items())}"
                )
                print(f"\033[96mbottle_rest:\033[0m method params: {params}")
            if params:
                data = request.json
                if not data:
                    data = {}
                for name, val in params.items():
                    if (
                        (name not in data)
                        and (name not in kwargs)
                        and (val.default == val.empty)
                    ):
                        response.status = 400
                        return {name: f"This feild is is required"}
                return callback(**data, **kwargs)
            return callback()

        return _wrapper

    def addResource(self, resource: Union[Type[Resource], Resource], *rules):
        for rule in rules:
            if self.debug:
                (f"Adding rescource '{rule}'")
            if callable(resource):
                resource = resource()
            # setattr(self, resource_cls.__name__, resource) Not sure if this is still needed
            self.resources.append(resource)
            for method in resource.Methods:
                func = resource.getFunction(method)
                cfg = resource.getRouteConfig(method)
                if func:
                    if self.debug:
                        print(
                            f"\033[96mbottle_rest:\033[0m Creating route {method.value} {rule} for method {func}"
                        )
                    self.app.route(rule, method.value, func, **cfg)
