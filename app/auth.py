"""Local account authentication with revocable, time-limited sessions."""
import hashlib
import re
import secrets
import sqlite3
import time
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from .db import get_db

bp = Blueprint("auth", __name__, url_prefix="/auth")
DUMMY_HASH = generate_password_hash(secrets.token_hex(32))


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def revoke_session():
    token = session.get("auth_token")
    if token:
        db = get_db()
        with db:
            db.execute("DELETE FROM auth_session WHERE token_hash=?", (token_hash(token),))
    session.clear()
    session["csrf_token"] = secrets.token_hex(32)


def load_user():
    g.user = None
    token = session.get("auth_token")
    if token:
        g.user = get_db().execute("SELECT u.id, u.email, u.display_name FROM app_user u JOIN auth_session s ON s.user_id=u.id WHERE s.token_hash=? AND s.expires_at>?", (token_hash(token), int(time.time()))).fetchone()
        if g.user is None:
            revoke_session()
    if request.blueprint in ("main", "community") and g.user is None:
        return redirect(url_for("auth.login"))


def limited(account):
    row = get_db().execute("SELECT * FROM login_attempt WHERE account=?", (account,)).fetchone()
    return row and row["started_at"] > int(time.time()) - 900 and row["attempts"] >= 5


def record_attempt(account):
    now = int(time.time())
    db = get_db()
    with db:
        db.execute("DELETE FROM login_attempt WHERE started_at<=?", (now-900,))
        db.execute("INSERT INTO login_attempt(account, attempts, started_at) VALUES (?,1,?) ON CONFLICT(account) DO UPDATE SET attempts=attempts+1", (account,now))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("main.index"))
    values = {}
    if request.method == "POST":
        values = {key: request.form.get(key, "").strip() for key in ("email", "display_name")}
        values["email"] = values["email"].lower()
        password = request.form.get("password", "")
        errors = []
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", values["email"]) or len(values["email"]) > 254:
            errors.append("Enter a valid email address.")
        if not 2 <= len(values["display_name"]) <= 60:
            errors.append("Display name must contain between 2 and 60 characters.")
        if not 12 <= len(password) <= 128:
            errors.append("Use a password containing between 12 and 128 characters.")
        if password != request.form.get("confirm_password"):
            errors.append("The passwords do not match.")
        account = "register:" + (request.remote_addr or "local")
        if limited(account):
            flash("Too many registration attempts. Try again in 15 minutes.", "error")
            return render_template("auth.html", registering=True, values=values), 429
        record_attempt(account)
        if not errors:
            try:
                db = get_db()
                with db:
                    db.execute("INSERT INTO app_user(email, display_name, password_hash) VALUES (?,?,?)", (values["email"], values["display_name"], generate_password_hash(password)))
            except sqlite3.IntegrityError:
                errors.append("Unable to create an account with those details. Try signing in or use another email.")
            else:
                flash("Account created. Sign in to continue.", "success")
                return redirect(url_for("auth.login"))
        for error in errors:
            flash(error, "error")
    return render_template("auth.html", registering=True, values=values), 422 if request.method == "POST" else 200


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("main.index"))
    values = {}
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()[:254]
        values["email"] = email
        account = "login:" + email
        if limited(account):
            flash("Too many sign-in attempts. Try again in 15 minutes.", "error")
            return render_template("auth.html", registering=False, values=values), 429
        user = get_db().execute("SELECT * FROM app_user WHERE email=?", (email,)).fetchone()
        password = request.form.get("password", "")
        valid = check_password_hash(user["password_hash"] if user else DUMMY_HASH, password[:129])
        if user and valid and len(password) <= 128:
            revoke_session()
            token = secrets.token_urlsafe(32)
            db = get_db()
            with db:
                db.execute("DELETE FROM auth_session WHERE expires_at<=?", (int(time.time()),))
                db.execute("INSERT INTO auth_session VALUES (?,?,?)", (token_hash(token), user["id"], int(time.time())+28800))
                db.execute("DELETE FROM login_attempt WHERE account=?", (account,))
            session["auth_token"] = token
            session["csrf_token"] = secrets.token_hex(32)
            return redirect(url_for("main.index"))
        record_attempt(account)
        flash("Email or password is incorrect.", "error")
        return render_template("auth.html", registering=False, values=values), 401
    return render_template("auth.html", registering=False, values=values)


@bp.post("/logout")
def logout():
    revoke_session()
    return redirect(url_for("auth.login"))
