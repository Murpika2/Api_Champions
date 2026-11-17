import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

# Valores SOLO para pruebas (no son secretos reales)
os.environ.setdefault("JWT_SECRET_KEY", "clave-de-pruebas-que-no-se-usa-en-produccion-1234567890")
os.environ.setdefault("ADMIN_PASSWORD", "Admin-Prueba-123")
os.environ.setdefault("VIEWER_PASSWORD", "Invitado-Prueba-123")

from app import create_app  # noqa: E402

ADMIN = {"username": "admin", "password": os.environ["ADMIN_PASSWORD"]}
VIEWER = {"username": "invitado", "password": os.environ["VIEWER_PASSWORD"]}


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "champions_test.db")


@pytest.fixture
def make_app(db_path):
    def _make(**overrides):
        cfg = {
            "TESTING": True,
            "DATABASE_PATH": db_path,
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD": ADMIN["password"],
            "VIEWER_USERNAME": "invitado",
            "VIEWER_PASSWORD": VIEWER["password"],
            "SEED_DEMO_DATA": True,
            "QUALIFICATION_SPOTS": 0,
        }
        cfg.update(overrides)
        return create_app(cfg)

    return _make


@pytest.fixture
def app(make_app):
    return make_app()


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, creds):
    res = client.post("/api/auth/login", json=creds)
    assert res.status_code == 200, res.json
    return {"Authorization": f"Bearer {res.json['data']['access_token']}"}


@pytest.fixture
def admin_headers(client):
    return login(client, ADMIN)


@pytest.fixture
def viewer_headers(client):
    return login(client, VIEWER)
