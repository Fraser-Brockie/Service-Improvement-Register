from app import repository


def test_banking_fields_round_trip_and_validation(client, app):
    values = dict(title="Improve fraud reporting", category="Customer", priority="High",
                  business_area="Retail banking", channel="Mobile app", owner="Fictional fraud team",
                  risk_category="Customer harm", approval_stage="Assessed", baseline="12 minutes",
                  target="8 minutes", review_date="2026-12-01")
    assert client.post("/items", data=values).status_code == 302
    page = client.get("/items/1")
    assert b"Fictional fraud team" in page.data
    assert b"8 minutes" in page.data
    values.update(approval_stage="Validated", actual="7 minutes")
    assert client.post("/items/1/edit", data=values).status_code == 302
    with app.app_context():
        assert repository.get_item(1)["actual"] == "7 minutes"
    values["channel"] = "Invalid channel"
    assert client.post("/items/1/edit", data=values).status_code == 422
    values["channel"] = "Branch"
    values["review_date"] = "invalid"
    assert client.post("/items", data=values).status_code == 422


def test_banking_demo_seed(app):
    result = app.test_cli_runner().invoke(args=["seed-demo"])
    assert result.exit_code == 0
    with app.app_context():
        assert repository.get_item(1)["business_area"] == "Retail banking"
    assert app.test_cli_runner().invoke(args=["seed-demo"]).exit_code != 0
