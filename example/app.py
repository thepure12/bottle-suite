# All config lives in bottle_suite.toml - see README.md for a walkthrough of
# what this app demonstrates and how to try it out.
from bottle_suite import BottleSuite

app = BottleSuite()

# The dashboard's own login (see README's "Auth: first-run setup") only ever
# authenticates the single admin account configured via /dashboard/setup, so
# tag it with an "admin" role claim - that's what lets the `["admin"]` role
# lists in bottle_suite.toml (as opposed to the plain `true` == "any logged
# in user" entries) mean something for this demo.
_authenticate = app.dashboard_token.authenticate


def authenticateWithRoles(username=None, password=None, **kwargs):
    user = _authenticate(username=username, password=password, **kwargs)
    if user:
        user["roles"] = ["admin"]
    return user


app.setTokenAuthFunction(authenticateWithRoles)

app.run(reloader=True)
