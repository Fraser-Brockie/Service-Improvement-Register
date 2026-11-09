from .db import get_db


def add_item(title, category, priority):
    db = get_db()
    cursor = db.execute(
        "INSERT INTO improvement (title, category, priority) VALUES (?, ?, ?)",
        (title, category, priority),
    )
    db.commit()
    return cursor.lastrowid


def list_items(status=None):
    db = get_db()
    if status:
        return db.execute(
            "SELECT * FROM improvement WHERE status = ? ORDER BY id DESC", (status,)
        ).fetchall()
    return db.execute("SELECT * FROM improvement ORDER BY id DESC").fetchall()


def update_status(item_id, status):
    db = get_db()
    cursor = db.execute("UPDATE improvement SET status = ? WHERE id = ?", (status, item_id))
    db.commit()
    return cursor.rowcount


def summary_counts():
    rows = get_db().execute(
        "SELECT status, priority, COUNT(*) AS total FROM improvement GROUP BY status, priority"
    ).fetchall()
    return rows
