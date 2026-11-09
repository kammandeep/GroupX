import sqlite3
from flask import current_app, g


def get_db():
    """One connection per request, reused until the request ends."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the database file and tables if they do not exist yet."""
    current_app.config["DATABASE"].parent.mkdir(parents=True, exist_ok=True)
    db = get_db()
    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf-8"))
    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

