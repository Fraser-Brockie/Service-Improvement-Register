import pytest
from app import create_app


@pytest.fixture()
def app(tmp_path):
    return create_app({"TESTING": True, "SECRET_KEY": "test", "DATABASE": str(tmp_path / "test.sqlite")})


@pytest.fixture()
def client(app):
    client = app.test_client()
    from app.db import get_db
    from werkzeug.security import generate_password_hash
    with app.app_context():
        db = get_db()
        with db:
            db.execute("INSERT INTO app_user(email,display_name,password_hash) VALUES (?,?,?)", ("demo@example.test", "Demo colleague", generate_password_hash("test-password-123")))
    client.get("/auth/login")
    with client.session_transaction() as session:
        token = session["csrf_token"]
    client.post("/auth/login", data={"email":"demo@example.test", "password":"test-password-123", "csrf_token":token})
    original_post = client.post

    def post(*args, **kwargs):
        client.get("/")
        with client.session_transaction() as session:
            token = session["csrf_token"]
        kwargs["data"] = {**kwargs.get("data", {}), "csrf_token": token}
        return original_post(*args, **kwargs)

    client.post = post
    return client
