"""First-run setup wizard.

Shown exactly once: while the instance has zero users, every request is
steered to /setup. The wizard creates the admin account and the initial
instance settings in one POST, signs the admin in, and then lets them add
their first feeds through the normal /feeds/add API.
"""
from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import login_user

from .auth import EMAIL_RE
from .models import User, db, set_setting

bp = Blueprint("setup", __name__)

# Once we've seen a user, skip the DB check on every request (per process).
_completed = {"done": False}


def needs_setup() -> bool:
    if _completed["done"]:
        return False
    if db.session.query(User.id).first() is not None:
        _completed["done"] = True
        return False
    return True


@bp.route("/setup")
def wizard():
    if not needs_setup():
        return redirect(url_for("auth.login"))
    return render_template("setup.html")


@bp.route("/setup", methods=["POST"])
def submit():
    if not needs_setup():
        return jsonify(error="This instance is already set up."), 409
    data = request.get_json(silent=True) or {}

    username = (data.get("username") or "").strip().lower()
    password = data.get("password") or ""
    if len(username) > 80 or not EMAIL_RE.match(username):
        return jsonify(error="Enter a valid email address."), 400
    if len(password) < 8:
        return jsonify(error="Passwords need at least 8 characters."), 400

    try:
        refresh = int(data.get("refresh_minutes", 15))
        retention = int(data.get("max_entries_per_feed", 300))
    except (TypeError, ValueError):
        return jsonify(error="Refresh interval and story cap must be numbers."), 400
    if not 0 <= refresh <= 1440:
        return jsonify(error="Refresh interval must be between 0 and 1440 minutes."), 400
    if not 20 <= retention <= 5000:
        return jsonify(error="Stories per feed must be between 20 and 5000."), 400

    admin = User(username=username, is_admin=True,
                 name=(data.get("name") or "").strip()[:120] or None)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()

    set_setting("registration_open", "1" if data.get("registration_open", True) else "0")
    set_setting("refresh_minutes", str(refresh))
    set_setting("max_entries_per_feed", str(retention))

    _completed["done"] = True
    login_user(admin, remember=True)
    return jsonify(ok=True)
