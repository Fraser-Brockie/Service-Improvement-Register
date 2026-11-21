import sqlite3
import pytest
from app import create_app
from app import repository
from app.db import get_db, init_db
from app.services import create_item, validate_item


def payload(**changes):
    return {
        "title": "Improve fictional handover",
        "category": "Process",
        "priority": "High",
        "description": "Reduce repeated entry",
        "due_date": "2020-01-01",
        **changes,
    }


def test_edit_detail_archive(client, app):
    assert client.get("/items/new").status_code == 200
    client.post("/items", data=payload())
    assert client.get("/items/1/edit").status_code == 200
    result = client.post("/items/1/edit", data=payload(title="Updated request"), follow_redirects=True)
    assert b"Updated request" in result.data
    assert b"details updated" in result.data
    assert client.post("/items/1/edit", data=payload(title="x")).status_code == 422
    assert client.post("/items/1/archive").status_code == 400
    assert client.post("/items/1/archive", data={"confirm": "archive"}).status_code == 302
    assert b"ARCHIVED" in client.get("/items/1").data
    assert client.get("/items/1/edit").status_code == 404
    assert client.post("/items/1/status", data={"status": "Done"}).status_code == 404
    with app.app_context():
        assert repository.get_item(1)["archived"] == 1
        assert repository.metrics()[0]["total"] == 0
        assert len(repository.history(1)) == 3


def test_csrf_and_headers(app):
    client = app.test_client()
    assert client.post("/items", data=payload()).status_code == 400
    client.get("/")
    assert client.post("/items", data=payload(csrf_token="wrong")).status_code == 400
    response = client.get("/")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "form-action 'self'" in response.headers["Content-Security-Policy"]
    assert "HttpOnly" in app.test_client().get("/").headers.get("Set-Cookie", "")
    assert client.post("/items", data={"description": "x" * 70000}).status_code == 413


def test_xss_and_sql_injection(client, app):
    client.post(
        "/items", data=payload(title="<script>alert(1)</script>", description="<img src=x onerror=alert(1)>")
    )
    response = client.get("/items/1")
    assert b"&lt;script&gt;" in response.data
    assert b"<img src=x" not in response.data
    response = client.get("/requests?q=' OR 1=1 --")
    assert response.status_code == 200
    with app.app_context():
        assert repository.metrics()[0]["total"] == 1


def test_search_sort_pages_metrics(app, client):
    with app.app_context():
        for n in range(23):
            create_item(f"Request {n:02}", "Process", "High", "searchable", "2020-01-01")
        repository.update_status(1, "Done")
        metrics, trend, recent = repository.metrics()
        assert metrics == {"total": 23, "completed": 1, "high": 22, "overdue": 22}
        assert sum(r["total"] for r in trend) == 23
        assert len(recent) == 6
        rows, count = repository.search_items({"q": "searchable", "sort": "oldest"}, 2)
        assert count == 23 and rows[0]["id"] == 11 and len(rows) == 10
        assert (
            repository.search_items({"status": "Done", "priority": "High", "category": "Process"}, 1)[1] == 1
        )
        assert repository.search_items({"q": "%"}, 1)[1] == 0
        assert repository.search_items({"sort": "title"}, 1)[0][0]["title"] == "Request 00"
        assert repository.search_items({"sort": "due"}, 1)[1] == 23
    for url in ("/?page=bad", "/?page=-3", "/?page=9999", "/requests?sort=malicious", "/?status=invalid"):
        assert client.get(url).status_code == 200
    assert b"Next" in client.get("/?page=2").data
    assert b"Previous" in client.get("/?page=2").data


@pytest.mark.parametrize(
    "changes",
    [{"title": "a" * 101}, {"description": "a" * 5001}, {"due_date": "2026-02-30"}, {"due_date": "bad"}],
)
def test_validation_boundaries(changes):
    data = payload(**changes)
    assert not validate_item(**data).valid


def test_missing_and_invalid_status(client):
    for url in ("/items/999", "/items/999/edit"):
        assert client.get(url).status_code == 404
    assert client.post("/items/999/status", data={"status": "Done"}).status_code == 404
    client.post("/items", data=payload())
    assert (
        b"Unsupported status"
        in client.post("/items/1/status", data={"status": "bad"}, follow_redirects=True).data
    )


def test_additive_migration(tmp_path):
    path = tmp_path / "legacy.sqlite"
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE improvement (id INTEGER PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL, priority TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'New', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    db.execute(
        "INSERT INTO improvement(title, category, priority) VALUES ('Retained record','Process','Low')"
    )
    db.commit()
    db.close()
    app = create_app({"TESTING": True, "DATABASE": str(path)})
    with app.app_context():
        init_db()
        assert repository.get_item(1)["title"] == "Retained record"
        assert repository.get_item(1)["updated_at"]
        assert get_db().execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            with get_db():
                get_db().execute("INSERT INTO activity(item_id,message) VALUES (999,'bad')")


def test_server_error(app):
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.get("/test-error")
    def crash():
        raise RuntimeError("private diagnostic")

    response = app.test_client().get("/test-error")
    assert response.status_code == 500
    assert b"private diagnostic" not in response.data


def test_unicode_csrf_and_noop_status(app):
    client = app.test_client()
    assert client.post("/items", data=payload(csrf_token="?")).status_code == 400
    with app.app_context():
        from app.services import change_status

        item_id, _ = create_item("Test unchanged status", "Process", "Low")
        change_status(item_id, "New")
        assert len(repository.history(item_id)) == 1
        assert not validate_item("Valid title", "Process", "Low", due_date="20260101").valid


def test_demo_command(app):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["seed-demo"]).exit_code == 0
    assert runner.invoke(args=["seed-demo"]).exit_code == 1
    with app.app_context():
        assert repository.metrics()[0]["total"] == 8


def test_creation_rolls_back_when_audit_fails(app):
    with app.app_context():
        db = get_db()
        db.execute(
            "CREATE TRIGGER reject_event BEFORE INSERT ON activity BEGIN SELECT RAISE(ABORT, 'test failure'); END"
        )
        with pytest.raises(sqlite3.IntegrityError):
            create_item("Must not persist", "Process", "High")
        assert repository.metrics()[0]["total"] == 0


def test_navigation_endpoints_and_register_pagination(client, app):
    from flask import url_for

    with app.test_request_context():
        assert url_for("main.index") == "/"
        assert url_for("main.register") == "/requests"
    with app.app_context():
        for n in range(11):
            create_item(f"Navigation item {n}", "Process", "Low")
    response = client.get("/requests")
    assert b'href="/requests?page=2' in response.data
    assert b"/requestsrequests" not in response.data
