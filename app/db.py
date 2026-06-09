import os
import sqlite3
from datetime import datetime
from flask import current_app, g
from werkzeug.security import generate_password_hash


def get_db():
    if "db" not in g:
        db_path = current_app.config["DATABASE_PATH"]
        if not os.path.isabs(db_path):
            db_path = os.path.join(current_app.root_path, "..", db_path)
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db_if_needed():
    db = get_db()
    schema_path = os.path.join(current_app.root_path, "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        db.executescript(f.read())

    admin_user = os.getenv("ADMIN_USER", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    existing = db.execute(
        "SELECT id FROM usuarios WHERE nome = ? AND deleted_at IS NULL", (admin_user,)
    ).fetchone()
    if existing is None:
        timestamp = now()
        db.execute(
            """
            INSERT INTO usuarios (nome, senha_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (admin_user, generate_password_hash(admin_password), timestamp, timestamp),
        )
    seed_tipo_banco(db)
    db.commit()

def seed_tipo_banco(db):
    bancos = ["SQL Server", "MySQL", "PostgreSQL", "Oracle", "SQLite"]
    timestamp = now()
    for banco in bancos:
        db.execute(
            """
            INSERT OR IGNORE INTO tipos_banco (nome, created_at, updated_at)
            VALUES (?, ?, ?)
            """,
            (banco, timestamp, timestamp),
        )
