"""The vendored plugins on a plain Bottle app, without the Bottler class:
no bottler.toml, no resources/ scan, no dashboard. Everything is wired by
hand."""
import os
import sqlite3
from datetime import datetime, timedelta, timezone

from bottle import Bottle, response
from bottler.plugins import API, CorsPlugin, JWTPlugin, Resource, sqlitePlugin

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "books.db")

if not os.path.exists(DB_PATH):
    con = sqlite3.connect(DB_PATH)
    con.executescript(
        """CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT NOT NULL);
           INSERT INTO books (title) VALUES ('Dune'), ('Emma');"""
    )
    con.close()


def login(username=None, password=None, **kwargs):
    # Demo-only check. Return the JWT payload, or None to reject.
    if username == "demo" and password == "demo-pw":
        return {"user": username, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    return None


app = Bottle()
app.install(CorsPlugin())
app.install(sqlitePlugin(DB_PATH))  # injects `db` into any callback that asks
# Demo-only key. JWTPlugin answers POST /token itself.
app.install(JWTPlugin("plain-bottle-demo-only-key-do-not-reuse", auth_func=login, token_path="token"))
api = API()
app.install(api)


@app.post("/token")
def token():
    pass  # never runs: JWTPlugin returns the token first


class Books(Resource):
    POST = {"roles": True}  # any valid token

    def get(self, db, book_id=None):
        if book_id is None:
            return {"books": db.execute("SELECT * FROM books").fetchall()}
        book = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        if not book:
            response.status = 404
            return {"message": "Book not found"}
        return book

    def post(self, db, title):
        db.execute("INSERT INTO books (title) VALUES (?)", (title,))
        response.status = 201
        return {"id": db.lastrowid, "title": title}


api.addResource(Books, "/books", "/books/<book_id>")

if __name__ == "__main__":
    app.run(port=8080, reloader=True)
