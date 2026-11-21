from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from . import repository
from .services import CATEGORIES, PRIORITIES, STATUSES, change_status, create_item, dashboard, validate_item

from .services import BANKING_FIELDS, validate_banking

bp = Blueprint("main", __name__)


@bp.app_context_processor
def options():
    return dict(categories=CATEGORIES, priorities=PRIORITIES, statuses=STATUSES, banking_fields=BANKING_FIELDS)


@bp.get("/requests", endpoint="register")
@bp.get("/")
def index():
    filters = {
        key: request.args.get(key, "").strip()[:100]
        for key in ("q", "status", "priority", "category", "sort")
    }
    page = min(1000000, max(1, request.args.get("page", 1, type=int) or 1))
    items, total = repository.search_items(filters, page)
    data = dashboard(include_items=False)
    data["items"] = items
    metrics, trend, recent = repository.metrics()
    return render_template(
        "index.html",
        data=data,
        metrics=metrics,
        trend=trend,
        recent=recent,
        filters=filters,
        page=page,
        total=total,
        pages=max(1, (total + 9) // 10),
        register=request.path == "/requests",
    )


def fields():
    return tuple(
        request.form.get(key, "").strip()
        for key in ("title", "category", "priority", "description", "due_date")
    )


@bp.route("/items/new", methods=["GET", "POST"])
@bp.post("/items")
def add():
    values = {}
    if request.method == "POST":
        values = request.form
        result = validate_banking(request.form)
        item_id = None
        if result.valid:
            item_id, result = create_item(*fields())
        if result.valid:
            repository.update_banking(item_id, request.form)
            flash("Improvement request recorded.", "success")
            return redirect(url_for("main.detail", item_id=item_id))
        for error in result.errors:
            flash(error, "error")
    return render_template("form.html", item=values, editing=False), 422 if request.method == "POST" else 200


def require_item(item_id):
    item = repository.get_item(item_id)
    if item is None:
        abort(404)
    return item


@bp.get("/items/<int:item_id>")
def detail(item_id):
    return render_template("detail.html", item=require_item(item_id), history=repository.history(item_id))


@bp.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
def edit(item_id):
    item = require_item(item_id)
    if item["archived"]:
        abort(404)
    if request.method == "POST":
        values = fields()
        result = validate_item(*values)
        if result.valid:
            result = validate_banking(request.form)
        if result.valid:
            repository.edit_item(item_id, *values[:-1], values[-1] or None)
            repository.update_banking(item_id, request.form)
            flash("Request updated.", "success")
            return redirect(url_for("main.detail", item_id=item_id))
        for error in result.errors:
            flash(error, "error")
        return render_template("form.html", item=request.form, editing=True), 422
    return render_template("form.html", item=item, editing=True)


@bp.post("/items/<int:item_id>/status")
def set_status(item_id):
    try:
        change_status(item_id, request.form.get("status", ""))
        flash("Status updated.", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    except LookupError:
        abort(404)
    return redirect(url_for("main.detail", item_id=item_id))


@bp.post("/items/<int:item_id>/archive")
def archive(item_id):
    require_item(item_id)
    if request.form.get("confirm") != "archive":
        abort(400, description="Confirm that you want to archive this request.")
    repository.archive_item(item_id)
    flash("Request archived. Its record and history have been retained.", "success")
    return redirect(url_for("main.index"))
