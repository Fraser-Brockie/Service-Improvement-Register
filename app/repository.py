from .db import get_db


def add_item(title, category, priority, description="", due_date=None):
    db = get_db()
    with db:
        cursor = db.execute(
            "INSERT INTO improvement (title, category, priority, description, due_date, updated_at) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (title, category, priority, description, due_date),
        )
        db.execute(
            "INSERT INTO activity (item_id, message) VALUES (?, ?)", (cursor.lastrowid, "Request created")
        )
    return cursor.lastrowid


def list_items(status=None):
    db = get_db()
    if status:
        return db.execute(
            "SELECT * FROM improvement WHERE archived = 0 AND status = ? ORDER BY id DESC", (status,)
        ).fetchall()
    return db.execute("SELECT * FROM improvement WHERE archived = 0 ORDER BY id DESC").fetchall()


def update_status(item_id, status):
    db = get_db()
    with db:
        cursor = db.execute(
            "UPDATE improvement SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND archived = 0",
            (status, item_id),
        )
        if cursor.rowcount:
            db.execute(
                "INSERT INTO activity (item_id, message) VALUES (?, ?)",
                (item_id, "Status changed to " + status),
            )
    return cursor.rowcount


def summary_counts():
    rows = (
        get_db()
        .execute(
            "SELECT status, priority, COUNT(*) AS total FROM improvement WHERE archived = 0 GROUP BY status, priority"
        )
        .fetchall()
    )
    return rows


def get_item(item_id):
    return get_db().execute("SELECT * FROM improvement WHERE id = ?", (item_id,)).fetchone()


def history(item_id):
    return (
        get_db().execute("SELECT * FROM activity WHERE item_id = ? ORDER BY id DESC", (item_id,)).fetchall()
    )


def edit_item(item_id, title, category, priority, description, due_date):
    db = get_db()
    with db:
        db.execute(
            """UPDATE improvement SET title=?, category=?, priority=?, description=?,
                   due_date=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND archived=0""",
            (title, category, priority, description, due_date, item_id),
        )
        db.execute(
            "INSERT INTO activity (item_id, message) VALUES (?, 'Request details updated')", (item_id,)
        )


def archive_item(item_id):
    db = get_db()
    with db:
        db.execute("UPDATE improvement SET archived=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (item_id,))
        db.execute("INSERT INTO activity (item_id, message) VALUES (?, 'Request archived')", (item_id,))


def search_items(filters, page, per_page=10):
    clauses, args = ["archived=0"], []
    for key in ("status", "priority", "category"):
        if filters.get(key):
            clauses.append(f"{key}=?")
            args.append(filters[key])
    if filters.get("q"):
        clauses.append("(instr(lower(title), lower(?)) > 0 OR instr(lower(description), lower(?)) > 0)")
        args.extend([filters["q"]] * 2)
    where = " AND ".join(clauses)
    order = {
        "newest": "id DESC",
        "oldest": "id ASC",
        "title": "title COLLATE NOCASE",
        "due": "due_date IS NULL, due_date",
    }.get(filters.get("sort"), "id DESC")
    db = get_db()
    total = db.execute(f"SELECT COUNT(*) FROM improvement WHERE {where}", args).fetchone()[0]
    rows = db.execute(
        f"SELECT * FROM improvement WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?",
        [*args, per_page, (page - 1) * per_page],
    ).fetchall()
    return rows, total


def metrics():
    db = get_db()
    counts = db.execute("""SELECT COUNT(*) total,
        COALESCE(SUM(status='Done'),0) completed,
        COALESCE(SUM(priority='High' AND status!='Done'),0) high,
        COALESCE(SUM(due_date < date('now') AND status!='Done'),0) overdue
        FROM improvement WHERE archived=0""").fetchone()
    trend = db.execute(
        "SELECT substr(created_at,1,10) day, COUNT(*) total FROM improvement WHERE archived=0 GROUP BY day ORDER BY day DESC LIMIT 30"
    ).fetchall()
    recent = db.execute(
        "SELECT a.*, i.title FROM activity a JOIN improvement i ON i.id=a.item_id ORDER BY a.id DESC LIMIT 6"
    ).fetchall()
    return dict(counts), [dict(r) for r in reversed(trend)], recent


def update_banking(item_id, values):
    from .services import BANKING_FIELDS
    clean = {key: values.get(key, "") for key in BANKING_FIELDS}
    db = get_db()
    with db:
        previous = get_item(item_id)
        if all(previous[key] == value for key, value in clean.items()):
            return
        assignments = ", ".join(f"{key}=?" for key in clean)
        db.execute(f"UPDATE improvement SET {assignments}, updated_at=CURRENT_TIMESTAMP WHERE id=? AND archived=0", [*clean.values(), item_id])
        db.execute("INSERT INTO activity (item_id, message) VALUES (?, ?)", (item_id, "Banking context, governance and outcome measures updated"))
