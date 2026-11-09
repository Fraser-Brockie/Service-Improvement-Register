from pathlib import Path
from flask import Flask, render_template

from .db import init_app as init_db_app
from .routes import bp


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="development-only-change-me",
        DATABASE=str(Path(app.instance_path) / "improvements.sqlite"),
    )
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    init_db_app(app)
    app.register_blueprint(bp)

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", message="The requested page was not found."), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template("error.html", message="An unexpected error occurred."), 500

    return app
