import _paths  # noqa: F401
import unittest
import webtest
from bottle_suite import BottleSuite

NONEXISTENT_CFG = "no_such_bottle_suite_cfg.toml"


class TestCors(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.bs = BottleSuite(
            cfg_file=NONEXISTENT_CFG,
            cors=True,
            rest=False,
            jwt=False,
            sqlite=False,
            sql=False,
            gen_res=False,
            gen_db=False,
        )
        self.bs.route("/thing", ["GET", "OPTIONS"], self._handler)
        self.app = webtest.TestApp(self.bs)

    def _handler(self):
        self.calls.append(True)
        return {"ok": True}

    def test_optionsPreflight_setsHeadersEmptyBody_doesNotCallHandler(self):
        resp = self.app.options("/thing")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")
        self.assertEqual(
            resp.headers.get("Access-Control-Allow-Methods"),
            "GET, POST, PUT, PATCH, OPTIONS, DELETE",
        )
        self.assertEqual(
            resp.headers.get("Access-Control-Allow-Headers"),
            "Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token, Authorization",
        )
        self.assertEqual(resp.body, b"")
        self.assertEqual(self.calls, [])

    def test_nonOptions_passesThrough_callsHandler(self):
        resp = self.app.get("/thing")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {"ok": True})
        self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")
        self.assertEqual(self.calls, [True])


if __name__ == "__main__":
    unittest.main()
