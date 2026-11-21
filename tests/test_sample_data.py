from datetime import date
from app.db import get_db
from app.services import create_item
from scripts.seed_realistic import EXAMPLES, seed


def test_realistic_samples_preserve_existing_and_are_repeatable(app):
    with app.app_context():
        create_item("Existing request", "Process", "Low")
        db = get_db()
        before = tuple(db.execute("SELECT * FROM improvement WHERE id=1").fetchone())
        assert seed(db, date(2026, 11, 10)) == len(EXAMPLES) == 24
        assert tuple(db.execute("SELECT * FROM improvement WHERE id=1").fetchone()) == before
        assert seed(db, date(2026, 11, 10)) == 0
        assert db.execute("SELECT COUNT(*) FROM improvement").fetchone()[0] == 25
        assert db.execute("SELECT COUNT(DISTINCT status) FROM improvement").fetchone()[0] == 3
        assert db.execute("SELECT COUNT(DISTINCT category) FROM improvement").fetchone()[0] == 4
        assert (
            db.execute(
                "SELECT COUNT(*) FROM improvement WHERE status!='Done' AND due_date<'2026-11-10'"
            ).fetchone()[0]
            == 3
        )
        assert (
            db.execute("SELECT COUNT(*) FROM activity WHERE item_id != 1 AND created_at>'2026-11-10 23:59:59'").fetchone()[0]
            == 0
        )
