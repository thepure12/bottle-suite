import os
import sqlite3

from bottler import Bottler

HERE = os.path.dirname(os.path.abspath(__file__))


def createDatabase(folder):
    """Build <folder>/data.db from <folder>/schema.sql on first run."""
    db_path = os.path.join(HERE, folder, "data.db")
    if os.path.exists(db_path):
        return
    with open(os.path.join(HERE, folder, "schema.sql")) as f:
        schema = f.read()
    con = sqlite3.connect(db_path)
    con.executescript(schema)
    con.close()


# Each mount's bottler.toml uses a sqlite path relative to the working
# directory, so run from this folder.
os.chdir(HERE)
createDatabase("billing")
createDatabase("inventory")

# This folder is on sys.path (it holds app.py), so billing_api and
# inventory_api import like installed packages.
app = Bottler()
app.run(port=8080, reloader=True)
