import time
from app.db import get_db
from werkzeug.security import check_password_hash


def post(client, url, data):
    client.get("/auth/login")
    with client.session_transaction() as state:
        data = {**data, "csrf_token":state["csrf_token"]}
    return client.post(url, data=data)


def register(client, **changes):
    return post(client, "/auth/register", {"email":"User@example.test", "display_name":"Test User", "password":"a-long-password-123", "confirm_password":"a-long-password-123", **changes})


def test_register_login_logout_and_revocation(app):
    client = app.test_client()
    for url in ("/", "/requests", "/items/new", "/community", "/community/ask", "/community/questions/1"):
        assert client.get(url).location.endswith("/auth/login")
    assert register(client).status_code == 302
    with app.app_context():
        user = get_db().execute("SELECT * FROM app_user").fetchone()
        assert user["email"] == "user@example.test"
        assert user["password_hash"] != "a-long-password-123"
        assert check_password_hash(user["password_hash"], "a-long-password-123")
    assert register(client).status_code == 422
    assert post(client,"/auth/login",{"email":"USER@example.test", "password":"a-long-password-123"}).status_code == 302
    assert client.get("/").status_code == 200
    assert b"Sign out" in client.get("/").data
    cookie = client.get_cookie("session").value
    assert client.get("/auth/logout").status_code == 405
    assert client.post("/auth/logout").status_code == 400
    assert post(client,"/auth/logout",{}).status_code == 302
    client.set_cookie("session",cookie)
    assert client.get("/").location.endswith("/auth/login")


def test_validation_throttle_and_expiry(app):
    client = app.test_client()
    assert register(client,password="short").status_code == 422
    assert register(client,email="invalid").status_code == 422
    assert register(client).status_code == 302
    for _ in range(5):
        assert post(client,"/auth/login",{"email":"user@example.test", "password":"wrong"}).status_code == 401
    assert post(client,"/auth/login",{"email":"user@example.test", "password":"a-long-password-123"}).status_code == 429
    with app.app_context():
        db=get_db()
        with db:
            db.execute("UPDATE login_attempt SET started_at=?",(int(time.time())-901,))
    assert post(client,"/auth/login",{"email":"user@example.test", "password":"a-long-password-123"}).status_code == 302
    with app.app_context():
        db=get_db()
        with db:
            db.execute("UPDATE auth_session SET expires_at=0")
    assert client.get("/community").location.endswith("/auth/login")


def test_signed_out_cannot_write(app):
    client=app.test_client()
    response=post(client,"/items",{"title":"Forbidden request", "category":"Process", "priority":"Low"})
    assert response.location.endswith("/auth/login")
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM improvement").fetchone()[0] == 0
