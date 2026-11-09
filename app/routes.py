from flask import Blueprint, flash, redirect, render_template, request, url_for
from .services import CATEGORIES, PRIORITIES, STATUSES, change_status, create_item, dashboard

bp = Blueprint("main", __name__)

@bp.get("/")
def index():
    selected = request.args.get("status", "")
    if selected and selected not in STATUSES:
        selected = ""
    return render_template(
        "index.html",
        data=dashboard(selected or None),
        categories=CATEGORIES,
        priorities=PRIORITIES,
        statuses=STATUSES,
        selected=selected,
    )

@bp.post("/items")
def add():
    _, result = create_item(
        request.form.get("title", ""),
        request.form.get("category", ""),
        request.form.get("priority", ""),
    )
    if not result.valid:
        for error in result.errors:
            flash(error, "error")
    else:
        flash("Improvement request recorded.", "success")
    return redirect(url_for("main.index"))

@bp.post("/items/<int:item_id>/status")
def set_status(item_id):
    try:
        change_status(item_id, request.form.get("status", ""))
        flash("Status updated.", "success")
    except (ValueError, LookupError) as exc:
        flash(str(exc), "error")
    return redirect(url_for("main.index"))
