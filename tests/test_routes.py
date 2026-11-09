def test_index(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Service Improvement Register" in response.data


def test_add_valid_item(client):
    response = client.post("/items", data={"title":"Automate routine check","category":"Technology","priority":"High"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Automate routine check" in response.data


def test_add_invalid_item(client):
    response = client.post("/items", data={"title":"x","category":"bad","priority":"bad"}, follow_redirects=True)
    assert b"Title must contain" in response.data


def test_filter_and_status_update(client):
    client.post("/items", data={"title":"Review handoff process","category":"Process","priority":"Medium"})
    response = client.post("/items/1/status", data={"status":"In Progress"}, follow_redirects=True)
    assert b"Status updated" in response.data
    filtered = client.get("/?status=In+Progress")
    assert b"Review handoff process" in filtered.data


def test_missing_page_uses_error_handler(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert b"requested page was not found" in response.data
