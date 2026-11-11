from pathlib import Path

from flask import current_app, g
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def init_app(app):
    database_url = app.config["SQLALCHEMY_DATABASE_URI"]
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args)

    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        database_path = database_url.removeprefix("sqlite:///")
        if database_path != ":memory:" and not database_path.startswith("file:"):
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)

    app.extensions["groupx_engine"] = engine
    app.extensions["groupx_session_factory"] = sessionmaker(
        bind=engine, expire_on_commit=False
    )
    app.teardown_appcontext(close_db)
    init_db(engine)


def get_engine() -> Engine:
    return current_app.extensions["groupx_engine"]


def get_db() -> Session:
    if "db" not in g:
        session_factory = current_app.extensions["groupx_session_factory"]
        g.db = session_factory()
    return g.db


def close_db(_error=None):
    session = g.pop("db", None)
    if session is not None:
        session.close()


def init_db(engine: Engine | None = None):
    from .models import Base

    target_engine = engine or get_engine()
    Base.metadata.create_all(target_engine)
