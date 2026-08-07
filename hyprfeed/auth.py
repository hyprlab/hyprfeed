import re

import requests
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func

from .models import User, db, get_setting

bp = Blueprint("auth", __name__)


def registration_open() -> bool:
    """Admin-panel toggle wins; the ALLOW_REGISTRATION env var is the default."""
    stored = get_setting("registration_open")
    if stored is not None:
        return stored == "1"
    return current_app.config["ALLOW_REGISTRATION"]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile() -> bool:
    """Validate the Turnstile token if Turnstile is configured; pass otherwise."""
    secret = current_app.config["TURNSTILE_SECRET_KEY"]
    if not secret:
        return True
    token = request.form.get("cf-turnstile-response", "")
    if not token:
        return False
    try:
        resp = requests.post(
            TURNSTILE_VERIFY_URL,
            data={
                "secret": secret,
                "response": token,
                "remoteip": request.headers.get("CF-Connecting-IP", request.remote_addr),
            },
            timeout=10,
        )
        return bool(resp.json().get("success"))
    except requests.RequestException:
        return False


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        if not verify_turnstile():
            flash("Verification failed. Please try again.", "error")
            return render_template("auth/login.html"), 400
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter(func.lower(User.username) == username.lower()).first()
        if user and user.check_password(password):
            login_user(user, remember=request.form.get("remember") == "on")
            dest = request.args.get("next")
            if dest and dest.startswith("/") and not dest.startswith("//"):
                return redirect(dest)
            return redirect(url_for("main.index"))
        flash("Wrong username or password.", "error")
        return render_template("auth/login.html"), 401
    return render_template("auth/login.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if not registration_open():
        flash("Registration is closed on this server.", "error")
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        if not verify_turnstile():
            flash("Verification failed. Please try again.", "error")
            return render_template("auth/register.html"), 400
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if len(username) > 80 or not EMAIL_RE.match(username):
            flash("Enter a valid email address.", "error")
        elif len(password) < 8:
            flash("Passwords need at least 8 characters.", "error")
        elif password != confirm:
            flash("Passwords don't match.", "error")
        elif User.query.filter(func.lower(User.username) == username).first():
            flash("An account with that email already exists.", "error")
        else:
            # The first account on a fresh instance becomes the admin.
            user = User(username=username, is_admin=User.query.count() == 0,
                        name=request.form.get("name", "").strip()[:120] or None)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("main.index"))
        return render_template("auth/register.html"), 400
    return render_template("auth/register.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
