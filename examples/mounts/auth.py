"""The parent app's /api/token login. Mounted packages never issue tokens;
they accept the parent's. Demo-only passwords."""
import hmac
from datetime import datetime, timedelta, timezone

USERS = {
    "fran": {"password": "demo-fran-pw", "roles": ["finance"]},
    "sam": {"password": "demo-sam-pw", "roles": []},
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
