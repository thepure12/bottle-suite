# Vendored from bottle-cors (https://github.com/thepure12/bottle-cors), MIT License.
# EnableCors renamed to CorsPlugin.
from bottle import response, request

class CorsPlugin(object):
    name = 'enable_cors'
    api = 2

    def __init__(self, origins=None):
        # None/falsy (the default) preserves the original unrestricted
        # behavior; a list restricts Access-Control-Allow-Origin to the
        # requesting Origin only when it's in the allowlist.
        self.origins = origins

    def apply(self, fn, context):
        def _enable_cors(*args, **kwargs):
            # set CORS headers
            if self.origins:
                origin = request.headers.get('Origin')
                if origin in self.origins:
                    response.headers['Access-Control-Allow-Origin'] = origin
            else:
                response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, OPTIONS, DELETE'
            response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token, Authorization'

            if request.method != 'OPTIONS':
                # actual request; reply with the actual response
                return fn(*args, **kwargs)

        return _enable_cors
