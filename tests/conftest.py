import pytest

from backend import db
from backend.app import create_app
from database.seed_data import populate_sample_data


@pytest.fixture
def app(tmp_path):
    """A fresh app with its own empty database file for every test."""
    return create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'test.db').as_posix()}"})


@pytest.fixture
def session(app):
    with app.app_context():
        yield db.get_db()


@pytest.fixture
def seeded(session):
    populate_sample_data(session)
    return session
