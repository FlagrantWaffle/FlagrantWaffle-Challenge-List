import os

os.environ.setdefault("SESSION_SECRET", "test-secret")

from fastapi.testclient import TestClient

import main


client = TestClient(
    main.app,
    base_url="http://localhost"
)


def test_healthz__200(monkeypatch):

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def execute(self, query):
            return None

    monkeypatch.setattr(
        main,
        "get_connection",
        lambda: FakeConnection()
    )

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_healthz_503(monkeypatch):

    def broken_connection():
        raise Exception("database unavailable")

    monkeypatch.setattr(
        main,
        "get_connection",
        broken_connection
    )

    response = client.get("/healthz")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Service unavailable"
    }


def test_admin_401():
    response = client.get("/admin")

    assert response.status_code == 401
    assert response.json() == {
        "detail": "You must be logged in"
    }