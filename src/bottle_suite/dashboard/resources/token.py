from ...plugins import Resource
from bottle import response
import hashlib
import hmac
import secrets


def hashPassword(password: str) -> str:
    salt = secrets.token_bytes(32)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return (salt + key).hex()


class DashboardToken(Resource):

    def __init__(self, app) -> None:
        self.app = app

    def isConfigured(self) -> bool:
        creds = self.app.cfg.get("dashboard")
        return bool(
            isinstance(creds, dict) and creds.get("username") and creds.get("password_hash")
        )

    def authenticate(self, username=None, password=None, **kwargs):
        creds = self.app.cfg.get("dashboard")
        if not isinstance(creds, dict):
            return None
        stored_username = creds.get("username")
        stored_hash = creds.get("password_hash")
        if not stored_username or not stored_hash:
            return None
        if not username or not password or username != stored_username:
            return None
        salt_key = bytes.fromhex(stored_hash)
        salt, key = salt_key[:32], salt_key[32:]
        new_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        if hmac.compare_digest(new_key, key):
            return {"user": stored_username}
        return None

    def options(self, *args, **kwargs):
        pass

    def get(self):
        return {"configured": self.isConfigured()}

    def post(self, username, password):
        if self.isConfigured():
            response.status = 403
            return {"message": "Dashboard admin credentials are already configured"}
        if not username or not password:
            response.status = 400
            return {"message": "username and password are required"}
        dashboard_cfg = self.app.cfg.get("dashboard")
        if not isinstance(dashboard_cfg, dict):
            dashboard_cfg = {}
        dashboard_cfg["username"] = username
        dashboard_cfg["password_hash"] = hashPassword(password)
        self.app.cfg["dashboard"] = dashboard_cfg
        self.app.saveConfig()
        self.app.reloadServer()
        return {"configured": True}
