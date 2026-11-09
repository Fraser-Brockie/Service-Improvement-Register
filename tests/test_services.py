import pytest
from app.services import change_status, create_item, dashboard, validate_item


def test_validation_rejects_bad_values():
    result = validate_item("x", "Unknown", "Urgent")
    assert result.valid is False
    assert len(result.errors) == 3


def test_create_and_dashboard(app):
    with app.app_context():
        item_id, result = create_item("Reduce duplicate entry", "Process", "High")
        assert item_id and result.valid
        data = dashboard()
        assert len(data["items"]) == 1
        assert data["priority_totals"]["High"] == 1


def test_change_status_and_invalid_status(app):
    with app.app_context():
        item_id, _ = create_item("Improve response template", "Quality", "Medium")
        change_status(item_id, "Done")
        assert dashboard("Done")["items"][0]["status"] == "Done"
        with pytest.raises(ValueError):
            change_status(item_id, "Deleted")
        with pytest.raises(LookupError):
            change_status(9999, "Done")
