import _paths  # noqa: F401
import unittest
from unittest import mock
import webtest
import jwt as pyjwt
from datetime import datetime, timedelta
from bottle_suite import BottleSuite
from bottle_suite.plugins.jwt import InvalidAlgorithm, AuthFailed, MethodNotAllowed

JWT_KEY = "secret"
NONEXISTENT_CFG = "no_such_bottle_suite_cfg.toml"


def make_app(**jwt_kwargs):
    cfg = {"jwt_key": JWT_KEY, **jwt_kwargs}
    bs = BottleSuite(
        cfg_file=NONEXISTENT_CFG,
        cors=True,
        rest=False,
        jwt=cfg,
        sqlite=False,
        sql=False,
        gen_res=False,
        gen_db=False,
    )
    return bs, webtest.TestApp(bs)


def valid_token(**payload_extra):
    payload = {"exp": datetime.utcnow() + timedelta(days=1), **payload_extra}
    return pyjwt.encode(payload, JWT_KEY, algorithm="HS256")


def expired_token():
    payload = {"exp": datetime.utcnow() - timedelta(seconds=10)}
    return pyjwt.encode(payload, JWT_KEY, algorithm="HS256")


class TestJWT(unittest.TestCase):
    def setUp(self):
        self.bs, self.app = make_app()

    def addProtected(self, roles=["admin"]):
        self.bs.route("/protected", "GET", lambda: {"ok": True}, roles=roles)

    def addUnprotected(self):
        self.bs.route("/unprotected", "GET", lambda: {"ok": True})

    def test_authHeaderMissing(self):
        self.addProtected()
        resp = self.app.get("/protected", expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json["message"], "Authorization header is expected")

    def test_invalidAuthScheme(self):
        self.addProtected()
        resp = self.app.get(
            "/protected", headers={"Authorization": "Basic abc"}, expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json["message"], "Authorization header must start with Bearer"
        )

    def test_tokenNotFound(self):
        self.addProtected()
        resp = self.app.get(
            "/protected", headers={"Authorization": "Bearer"}, expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json["message"], "Token not found")

    def test_invalidHeader(self):
        self.addProtected()
        resp = self.app.get(
            "/protected",
            headers={"Authorization": "Bearer a b"},
            expect_errors=True,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json["message"], "Authorization header must be Bearer + ' ' + <token>"
        )

    def test_methodNotAllowed_getToken(self):
        resp = self.app.get("/token", expect_errors=True)
        self.assertEqual(resp.status_code, 405)
        self.assertEqual(
            resp.json["message"], "Method Not Allowed, use POST for authentication"
        )

    def test_authFailed_authFuncReturnsFalsy(self):
        self.bs.jwt.token_paths["token"] = lambda: None
        resp = self.app.post("/token", expect_errors=True)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json["message"], "Authentication failed")

    def test_postToken_defaultAuthFunc_returnsToken(self):
        resp = self.app.post("/token")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("token", resp.json)

    def test_invalidAudience_roleMismatch(self):
        self.addProtected(roles=["admin"])
        token = valid_token()  # no "roles" claim -> user_roles defaults to [True]
        resp = self.app.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
            expect_errors=True,
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(
            resp.json["message"], "You do not have permission to access this content"
        )

    def test_expiredSignature(self):
        self.addProtected()
        token = expired_token()
        resp = self.app.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
            expect_errors=True,
        )
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json["message"], "Signature has expired")

    def test_decodeToken_unprotectedRoute_badTokenStillServed(self):
        self.addUnprotected()
        resp = self.app.get(
            "/unprotected", headers={"Authorization": "Bearer garbage"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {"ok": True})

    def test_decodeToken_unprotectedRoute_noHeaderStillServed(self):
        self.addUnprotected()
        resp = self.app.get("/unprotected")
        self.assertEqual(resp.status_code, 200)

    def test_checkRoles_boolTrue_anyValidTokenOk(self):
        self.addProtected(roles=True)
        token = valid_token()
        resp = self.app.get(
            "/protected", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(resp.status_code, 200)

    def test_checkRoles_listRoles_matches(self):
        self.addProtected(roles=["admin", "user"])
        token = valid_token(roles=["user"])
        resp = self.app.get(
            "/protected", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(resp.status_code, 200)

    def test_checkRoles_callableRoles(self):
        self.addProtected(roles=lambda: ["admin"])
        token = valid_token(roles=["admin"])
        resp = self.app.get(
            "/protected", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(resp.status_code, 200)

    def test_addTokenPath_customPath(self):
        self.bs.jwt.addTokenPath("register", lambda: {"exp": datetime.utcnow() + timedelta(days=1)})
        self.bs.route(
            "/register", ["GET", "POST", "OPTIONS"], self.bs.jwt.token_paths["register"]
        )
        resp = self.app.post("/register")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("token", resp.json)

    def test_usersCurrent_alwaysHardcodedDefault(self):
        resp = self.app.get("/users/current")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {"user": "default"})

    def test_handleException_failRedirectSet_redirects(self):
        bs, app = make_app(fail_redirect="/login")
        bs.route("/protected", "GET", lambda: {"ok": True}, roles=["admin"])
        resp = app.get("/protected", expect_errors=True)
        self.assertIn(resp.status_code, (302, 303, 307))
        self.assertTrue(resp.headers.get("Location", "").endswith("/login"))

    def test_handleException_failRedirect_doesNotBypassOtherErrors(self):
        # InvalidAuthScheme/TokenNotFound/InvalidHeader always raise directly,
        # never going through handleException/fail_redirect.
        bs, app = make_app(fail_redirect="/login")
        bs.route("/protected", "GET", lambda: {"ok": True}, roles=["admin"])
        resp = app.get(
            "/protected", headers={"Authorization": "Basic abc"}, expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)

    def test_handleException_noFailRedirect_raises(self):
        self.addProtected()
        resp = self.app.get("/protected", expect_errors=True)
        self.assertEqual(resp.status_code, 400)

    def test_debugMode_printsDiagnostics(self):
        bs, app = make_app(debug=True)
        bs.route("/protected", "GET", lambda: {"ok": True}, roles=["admin"])
        token = valid_token(roles=["admin"])
        resp = app.get("/protected", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status_code, 200)
        resp2 = app.post("/token")
        self.assertEqual(resp2.status_code, 200)

    def test_addTokenPath_defaultAuthFunc(self):
        self.bs.jwt.addTokenPath("register")
        self.assertIn("register", self.bs.jwt.token_paths)
        payload = self.bs.jwt.token_paths["register"]()
        self.assertIn("exp", payload)

    def test_invalidAlgorithm_directConstruction(self):
        # Defined but never raised anywhere in application code (confirmed
        # by reading jwt.py) -- exercised directly here for coverage.
        err = InvalidAlgorithm()
        self.assertEqual(err.status_code, 400)
        self.assertEqual(
            err.body["message"], "The specified alg value is not allowed"
        )

    class _FakeRoute:
        def __init__(self, method):
            self.method = method

    def test_handleTokenPath_otherMethod_implicitNone(self):
        result = self.bs.jwt.handleTokenPath("token", self._FakeRoute("PUT"))
        self.assertIsNone(result)

    def test_handleTokenPath_postFalsyToken_authFailed(self):
        # createToken() normally raises AuthFailed itself when the payload is
        # falsy, so a falsy `token` here is otherwise unreachable via normal
        # flow -- exercised via direct monkeypatch for coverage.
        with mock.patch.object(self.bs.jwt, "createToken", return_value=None):
            with self.assertRaises(AuthFailed):
                self.bs.jwt.handleTokenPath("token", self._FakeRoute("POST"))


if __name__ == "__main__":
    unittest.main()
