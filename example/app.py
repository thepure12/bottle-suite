# All config lives in bottle_suite.toml - see README.md for a walkthrough of
# what this app demonstrates and how to try it out.
import hashlib
import hmac

from bottle_suite import BottleSuite

app = BottleSuite()

# /token is this app's own REST API login - the dashboard UI authenticates
# separately, through its own internal /dashboard/token (backed by the
# single admin account bootstrapped via /dashboard/setup), so it never
# shares credentials or roles with the API below.
#
# Two demo accounts so the README's role-gating walkthrough (POST vs DELETE
# on /tasks) has a non-admin user to demonstrate a 403 with, not just an
# admin/no-token pair.
#
# Passwords and hashes below are demo-only - regenerate before reusing this
# for anything beyond this local example.
USERS = {
    "admin": {
        "password_hash": (
            "cffe3610ab4b0d5bf1ea51399c7cb5676e3db59ba9edfb5fe3661d558dc875e"
            "a49abe0105adf9b6003b4352a6fa68b6aab627ddc4ecd10e47d8826700b91d9"
            "01"
        ),
        "roles": ["admin"],
    },
    "alice": {
        "password_hash": (
            "4ca24b74ba282fb41cfd485bedc98754e9917cdcabc3a003235b65a2e4ec2cc"
            "90aba92523a28bdc49fcac55e8e2eee68c1cb87cca0e34a5c15151e998e85c8"
            "83"
        ),
        "roles": [],
    },
}


def verifyPassword(password: str, stored_hash: str) -> bool:
    salt_key = bytes.fromhex(stored_hash)
    salt, key = salt_key[:32], salt_key[32:]
    new_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return hmac.compare_digest(new_key, key)


def authenticate(username=None, password=None, **kwargs):
    user = USERS.get(username)
    if not user or not password:
        return None
    if not verifyPassword(password, user["password_hash"]):
        return None
    return {"user": username, "roles": user["roles"]}


app.setTokenAuthFunction(authenticate)

app.run(reloader=True)
