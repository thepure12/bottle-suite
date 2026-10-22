"""Found automatically at the project root and wired up as the /token
login. Return the JWT payload on success, or None to reject.

The users and passwords below are demo-only. A real project checks
password hashes in its own user store (see examples/task_tracker/app.py
for a PBKDF2 version)."""
import hmac
from datetime import datetime, timedelta, timezone

USERS = {
    "admin": {"password": "demo-admin-pw", "roles": ["admin"]},
    "alice": {"password": "demo-alice-pw", "roles": []},
}


def authenticate(username=None, password=None, **kwargs):
    user = USERS.get(username)
    if not user or not password:
        return None
    if not hmac.compare_digest(password, user["password"]):
        return None
    return {
        "user": username,
        "roles": user["roles"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=8),
    }
