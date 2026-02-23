from datetime import datetime, timezone

import pytest
from sqlalchemy.pool import StaticPool

from backend.extensions import db
from backend.helpchain_backend.src.app import create_app


@pytest.fixture()
def app():
    class TestConfig:
        TESTING = True
        SQLALCHEMY_DATABASE_URI = "sqlite://"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        SQLALCHEMY_ENGINE_OPTIONS = {
            "poolclass": StaticPool,
            "connect_args": {"check_same_thread": False},
        }
        WTF_CSRF_ENABLED = False

    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def session(app):
    return db.session


def utcnow():
    return datetime.now(timezone.utc)
