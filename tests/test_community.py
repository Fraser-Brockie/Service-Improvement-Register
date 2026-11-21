from app.db import get_db, init_db


def question(**changes):
    return dict(title="How can we improve payment handovers?", body="We tried a shared checklist. What practical steps would help?", author="Demo colleague", topic="Payments", **changes)


def test_question_and_answer_flow(client, app):
    assert client.get("/community").status_code == 200
    assert client.get("/community/ask").status_code == 200
    response = client.post("/community/ask", data=question())
    assert response.status_code == 302
    assert response.location.endswith("/community/questions/1")
    assert b"Demo colleague" in client.get(response.location).data
    assert b"payment handovers" in client.get("/community?q=payment&topic=Payments&unanswered=1").data
    response = client.post("/community/questions/1", data=dict(body="Assign a named team and agree an escalation time.", author="Demo helper"), follow_redirects=True)
    assert b"Assign a named team" in response.data
    assert b"payment handovers" not in client.get("/community?unanswered=1").data
    assert b"payment handovers" not in client.get("/community?topic=Accessibility").data
    with app.app_context():
        init_db()
        assert get_db().execute("SELECT COUNT(*) FROM answer").fetchone()[0] == 1


def test_validation_csrf_and_escaping(client, app):
    bad = question()
    bad.update(title="short", topic="invalid")
    response = client.post("/community/ask", data=bad)
    assert response.status_code == 422
    assert b"shared checklist" in response.data
    assert client.post("/community/ask", data=question()).status_code == 302
    assert client.post("/community/questions/1", data=dict(body="short", author="x")).status_code == 422
    assert client.get("/community/questions/999").status_code == 404
    assert client.post("/community/questions/999", data={}).status_code == 404
    assert app.test_client().post("/community/ask", data=question()).status_code == 400
    assert app.test_client().post("/community/questions/1", data={}).status_code == 400
    response = client.post("/community/questions/1", data=dict(body="<script>alert(1)</script>", author="<b>Demo</b>"), follow_redirects=True)
    assert b"&lt;script&gt;" in response.data
    assert b"<script>alert(1)</script>" not in response.data
    assert b"&lt;b&gt;Demo" not in response.data
    with app.app_context():
        row = get_db().execute("SELECT author,user_id FROM answer").fetchone()
        assert row["author"] == "Demo colleague" and row["user_id"] is not None
    assert client.get("/community?q=' OR 1=1 --").status_code == 200


def test_pagination_and_interface_separators(client):
    for n in range(11):
        values = question()
        values["title"] = f"Question number {n} about payment support"
        client.post("/community/ask", data=values)
    assert b"Question number 0 about" not in client.get("/community").data
    assert b"Question number 0 about" in client.get("/community?page=2").data
    assert b"Page 1 of" in client.get("/community?page=invalid").data
    home = client.get("/").data
    assert b"GROUP ? DEMONSTRATION" not in home
    assert b"demo ? Fictional" not in home
    assert b"Community Q&amp;A" in home
