"""Community questions and answers for the local demonstration."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from .db import get_db

bp = Blueprint("community", __name__, url_prefix="/community")
TOPICS = ("Customer support", "Payments", "Digital banking", "Process and controls", "Accessibility", "General")


def validate_post(values, question=False):
    errors = []
    if not 2 <= len(values.get("author", "")) <= 60:
        errors.append("Display name must contain between 2 and 60 characters.")
    minimum = 20 if question else 10
    if not minimum <= len(values.get("body", "")) <= 10000:
        errors.append(f"Details must contain between {minimum} and 10,000 characters.")
    if question:
        if not 10 <= len(values.get("title", "")) <= 160:
            errors.append("Question title must contain between 10 and 160 characters.")
        if values.get("topic") not in TOPICS:
            errors.append("Choose a valid topic.")
    return errors


@bp.get("")
@bp.get("/")
def index():
    query = request.args.get("q", "").strip()[:160]
    topic = request.args.get("topic", "")
    unanswered = request.args.get("unanswered") == "1"
    page = max(1, min(request.args.get("page", 1, type=int) or 1, 1000000))
    clauses, args = [], []
    if query:
        clauses.append("(instr(lower(q.title),lower(?))>0 OR instr(lower(q.body),lower(?))>0)")
        args.extend([query, query])
    if topic:
        clauses.append("q.topic=?")
        args.append(topic)
    if unanswered:
        clauses.append("NOT EXISTS (SELECT 1 FROM answer a WHERE a.question_id=q.id)")
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM question q" + where, args).fetchone()[0]
    questions = db.execute("SELECT q.*, (SELECT COUNT(*) FROM answer a WHERE a.question_id=q.id) answer_count FROM question q" + where + " ORDER BY q.id DESC LIMIT 10 OFFSET ?", [*args, (page-1)*10]).fetchall()
    stats = db.execute("SELECT (SELECT COUNT(*) FROM question) questions, (SELECT COUNT(*) FROM answer) answers, (SELECT COUNT(*) FROM question q WHERE NOT EXISTS (SELECT 1 FROM answer a WHERE a.question_id=q.id)) unanswered").fetchone()
    return render_template("community.html", questions=questions, topics=TOPICS, query=query, topic=topic, unanswered=unanswered, page=page, pages=max(1,(total+9)//10), total=total, stats=stats)


@bp.route("/ask", methods=["GET", "POST"])
def ask():
    values = {}
    if request.method == "POST":
        values = {key: request.form.get(key, "").strip() for key in ("title", "body", "author", "topic")}
        values["author"] = g.user["display_name"]
        errors = validate_post(values, question=True)
        if not errors:
            db = get_db()
            with db:
                row = db.execute("INSERT INTO question (title, body, author, topic, user_id) VALUES (?, ?, ?, ?, ?)", [*[values[key] for key in ("title", "body", "author", "topic")], g.user["id"]])
            flash("Your question has been posted.", "success")
            return redirect(url_for("community.detail", question_id=row.lastrowid))
        for error in errors:
            flash(error, "error")
    return render_template("question_form.html", values=values, topics=TOPICS), 422 if request.method == "POST" else 200


@bp.route("/questions/<int:question_id>", methods=["GET", "POST"])
def detail(question_id):
    db = get_db()
    question = db.execute("SELECT * FROM question WHERE id=?", (question_id,)).fetchone()
    if question is None:
        abort(404)
    values = {}
    if request.method == "POST":
        values = {key: request.form.get(key, "").strip() for key in ("body", "author")}
        values["author"] = g.user["display_name"]
        errors = validate_post(values)
        if not errors:
            with db:
                db.execute("INSERT INTO answer (question_id, body, author, user_id) VALUES (?, ?, ?, ?)", (question_id, values["body"], values["author"], g.user["id"]))
            flash("Your answer has been posted.", "success")
            return redirect(url_for("community.detail", question_id=question_id) + "#answers")
        for error in errors:
            flash(error, "error")
    answers = db.execute("SELECT * FROM answer WHERE question_id=? ORDER BY id", (question_id,)).fetchall()
    return render_template("question_detail.html", question=question, answers=answers, values=values), 422 if request.method == "POST" else 200
