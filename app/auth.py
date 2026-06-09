from functools import wraps
from flask import flash, redirect, session, url_for


def is_admin():
    return bool(session.get("admin_id"))


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if not is_admin():
            flash("Faça login como administrador para acessar essa área.", "warning")
            return redirect(url_for("main.login"))
        return view(**kwargs)
    return wrapped_view
