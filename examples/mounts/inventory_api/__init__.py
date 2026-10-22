"""Inventory service. Served under /api/inventory/ when mounted."""

settings = {"low_stock_threshold": 5}


def configure(app):
    # Runs last, like a project's hooks.py. app is this package's own
    # Bottler: app.cfg is inventory/bottler.toml and app.base_dir is the
    # inventory/ folder.
    settings["low_stock_threshold"] = app.cfg.get("low_stock_threshold", 5)
