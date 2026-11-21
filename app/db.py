import sqlite3
from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS improvement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL CHECK(length(title) BETWEEN 3 AND 100),
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'New',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    get_db().executescript(SCHEMA)
    db = get_db()
    columns = {row[1] for row in db.execute("PRAGMA table_info(improvement)")}
    for name, definition in {
        "description": "TEXT NOT NULL DEFAULT ''",
        **{key: "TEXT NOT NULL DEFAULT ''" for key in ("business_area", "customer_journey", "channel", "owner", "risk_category", "customer_outcome", "success_measure", "baseline", "target", "actual", "approval_stage", "approver", "review_date")},
        "due_date": "TEXT",
        "updated_at": "TEXT",
        "archived": "INTEGER NOT NULL DEFAULT 0",
    }.items():
        if name not in columns:
            db.execute(f"ALTER TABLE improvement ADD COLUMN {name} {definition}")
    db.execute("UPDATE improvement SET updated_at = created_at WHERE updated_at IS NULL")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS app_user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            display_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS auth_session (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES app_user(id),
            expires_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS login_attempt (
            account TEXT PRIMARY KEY,
            attempts INTEGER NOT NULL DEFAULT 0,
            started_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS activity (
            id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL REFERENCES improvement(id),
            message TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_improvement_active_status ON improvement(archived, status);
        CREATE TABLE IF NOT EXISTS question (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL CHECK(length(title) BETWEEN 10 AND 160),
            body TEXT NOT NULL CHECK(length(body) BETWEEN 20 AND 10000),
            author TEXT NOT NULL CHECK(length(author) BETWEEN 2 AND 60),
            topic TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS answer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL REFERENCES question(id),
            body TEXT NOT NULL CHECK(length(body) BETWEEN 10 AND 10000),
            author TEXT NOT NULL CHECK(length(author) BETWEEN 2 AND 60),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_answer_question ON answer(question_id, id);
        CREATE INDEX IF NOT EXISTS idx_activity_item ON activity(item_id, id);
    """)
    for table in ("question", "answer"):
        existing = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
        if "user_id" not in existing:
            db.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER REFERENCES app_user(id)")
    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()
