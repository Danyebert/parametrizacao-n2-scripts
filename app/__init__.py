import os
from flask import Flask
from dotenv import load_dotenv

from .db import close_db, init_db_if_needed
from .filters import nl2br
from .routes import bp


def create_app():
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-change-me"),
        DATABASE_PATH=os.getenv("DATABASE_PATH", "instance/parametrizacao_n2.sqlite3"),
        UPLOAD_FOLDER=os.path.join(app.root_path, "static", "uploads"),
        MAX_CONTENT_LENGTH=int(os.getenv("MAX_CONTENT_LENGTH_MB", "8")) * 1024 * 1024,
    )

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    app.teardown_appcontext(close_db)
    app.jinja_env.filters["nl2br"] = nl2br
    app.register_blueprint(bp)

    with app.app_context():
        init_db_if_needed()

    return app
