from pathlib import Path
import os
import secrets
import hmac
from flask import Flask, render_template, request, session, abort

from .db import init_app as init_db_app
from .routes import bp


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    secret = os.environ.get("SECRET_KEY")
    if not secret and not (test_config and test_config.get("SECRET_KEY")):
        secret_path = Path(app.instance_path) / ".session-secret"
        try:
            with secret_path.open("x", encoding="utf-8") as handle:
                handle.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        secret = secret_path.read_text(encoding="utf-8").strip()
    app.config.from_mapping(
        SECRET_KEY=secret,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("HTTPS_ONLY") == "1",
        MAX_CONTENT_LENGTH=64 * 1024,
        TEMPLATES_AUTO_RELOAD=True,
        SEND_FILE_MAX_AGE_DEFAULT=0,
        DATABASE=os.environ.get("DATABASE") or str(Path(app.instance_path) / "improvements.sqlite"),
    )
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    init_db_app(app)
    app.register_blueprint(bp)
    from .community import bp as community_bp
    app.register_blueprint(community_bp)
    from .commands import register_commands

    register_commands(app)

    @app.before_request
    def protect_forms():
        session.setdefault("csrf_token", secrets.token_hex(32))
        if request.method == "POST":
            token = request.form.get("csrf_token", "")
            if not hmac.compare_digest(token.encode(), session["csrf_token"].encode()):
                abort(400, description="The form expired. Reload the page and try again.")

    from .auth import bp as auth_bp, load_user
    app.register_blueprint(auth_bp)
    app.before_request(load_user)

    @app.after_request
    def secure_headers(response):
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' https://cdn.jsdelivr.net; script-src 'self' https://cdn.jsdelivr.net; img-src 'self' data:; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        app.logger.info(
            "request method=%s path=%s status=%s", request.method, request.path, response.status_code
        )
        return response

    @app.errorhandler(400)
    @app.errorhandler(413)
    def bad_request(error):
        return render_template("error.html", message=error.description), error.code

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", message="The requested page was not found."), 404

    @app.errorhandler(500)
    def server_error(error):
        app.logger.error("request_failed", exc_info=error)
        return render_template("error.html", message="An unexpected error occurred."), 500

    return app
