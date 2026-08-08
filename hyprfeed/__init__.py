import logging
import os
import secrets
import threading
import time
from datetime import datetime

from flask import Flask, redirect, request, session, url_for
from flask_login import LoginManager

from .config import Config
from .models import User, db, utcnow

__version__ = "1.7.3"

logging.basicConfig(level=logging.INFO)

_refresher_started = threading.Lock()
_refresher_running = False


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from . import auth, main, setup
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(setup.bp)

    @app.before_request
    def steer_to_setup():
        """A fresh install (zero users) goes to the wizard, nowhere else."""
        if request.endpoint in ("setup.wizard", "setup.submit", "static"):
            return None
        if setup.needs_setup():
            return redirect(url_for("setup.wizard"))
        return None

    # ---- CSRF (lightweight, session-token based) ----
    def csrf_token() -> str:
        if "_csrf" not in session:
            session["_csrf"] = secrets.token_hex(16)
        return session["_csrf"]

    @app.before_request
    def check_csrf():
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return None
        sent = request.headers.get("X-CSRF") or request.form.get("_csrf")
        if not sent or sent != session.get("_csrf"):
            return {"error": "Invalid or missing CSRF token."}, 400
        return None

    @app.after_request
    def no_stale_html(resp):
        # Dynamic pages must never be replayed from browser cache — a stale
        # page briefly shows stories the user has since hidden or read.
        if resp.mimetype == "text/html":
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.template_global()
    def static_url(filename: str) -> str:
        """Static URL with an mtime cache-buster so redeploys invalidate
        browser caches immediately."""
        from flask import url_for
        try:
            version = int(os.path.getmtime(os.path.join(app.static_folder, filename)))
        except OSError:
            version = 0
        return url_for("static", filename=filename, v=version)

    @app.context_processor
    def inject_globals():
        return {
            "csrf_token": csrf_token,
            "turnstile_site_key": app.config["TURNSTILE_SITE_KEY"],
            "allow_registration": auth.registration_open(),
            "app_version": __version__,
        }

    from . import about_docs
    app.jinja_env.globals["app_changelog"] = about_docs.changelog

    # ---- Template filters ----
    @app.template_filter("ago")
    def ago(dt: datetime) -> str:
        seconds = int((utcnow() - dt).total_seconds())
        if seconds < 60:
            return "now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days < 7:
            return f"{days}d ago"
        if days < 365:
            return dt.strftime("%b %-d")
        return dt.strftime("%b %-d, %Y")

    @app.template_filter("readtime")
    def readtime(words: int) -> str:
        return f"{max(1, round((words or 0) / 220))} min"

    with app.app_context():
        db.create_all()
        _migrate(app)

    _start_refresher(app)
    return app


def _migrate(app: Flask) -> None:
    """Tiny in-place migrations for databases created by older versions."""
    from sqlalchemy import inspect, text

    columns = {c["name"] for c in inspect(db.engine).get_columns("users")}
    if "is_admin" not in columns:
        db.session.execute(
            text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0")
        )
        # Pre-admin databases: the earliest account becomes the admin.
        first_id = db.session.execute(
            text("SELECT id FROM users ORDER BY id LIMIT 1")
        ).scalar()
        if first_id is not None:
            db.session.execute(
                text("UPDATE users SET is_admin = 1 WHERE id = :id"), {"id": first_id}
            )
        db.session.commit()
        app.logger.info("migrated: added users.is_admin")

    feed_columns = {c["name"] for c in inspect(db.engine).get_columns("feeds")}
    if "kind" not in feed_columns:
        db.session.execute(
            text("ALTER TABLE feeds ADD COLUMN kind VARCHAR(10) NOT NULL DEFAULT 'rss'")
        )
        db.session.commit()
        app.logger.info("migrated: added feeds.kind")

    user_columns = {c["name"] for c in inspect(db.engine).get_columns("users")}
    if "name" not in user_columns:
        db.session.execute(text("ALTER TABLE users ADD COLUMN name VARCHAR(120)"))
        db.session.commit()
        app.logger.info("migrated: added users.name")

    sub_columns = {c["name"] for c in inspect(db.engine).get_columns("subscriptions")}
    if "position" not in sub_columns:
        db.session.execute(text("ALTER TABLE subscriptions ADD COLUMN position INTEGER"))
        # Backfill: current alphabetical order becomes the starting order.
        rows = db.session.execute(text(
            "SELECT s.id, s.user_id FROM subscriptions s JOIN feeds f ON f.id = s.feed_id "
            "ORDER BY s.user_id, LOWER(COALESCE(NULLIF(s.custom_title, ''), f.title, f.url))"
        )).fetchall()
        counters: dict = {}
        for sub_id, user_id in rows:
            pos = counters.get(user_id, 0)
            counters[user_id] = pos + 1
            db.session.execute(
                text("UPDATE subscriptions SET position = :pos WHERE id = :id"),
                {"pos": pos, "id": sub_id},
            )
        db.session.commit()
        app.logger.info("migrated: added subscriptions.position")

    sub_columns = {c["name"] for c in inspect(db.engine).get_columns("subscriptions")}
    if "group_id" not in sub_columns:
        db.session.execute(text("ALTER TABLE subscriptions ADD COLUMN group_id INTEGER"))
        db.session.commit()
        app.logger.info("migrated: added subscriptions.group_id")

    # Sweep read/star marks orphaned by pruning before cleanup existed.
    swept = 0
    for table in ("read_marks", "stars", "hidden_entries"):
        result = db.session.execute(
            text(f"DELETE FROM {table} WHERE entry_id NOT IN (SELECT id FROM entries)")
        )
        swept += result.rowcount or 0
    if swept:
        db.session.commit()
        app.logger.info("cleaned up %d orphaned read/star marks", swept)


def _start_refresher(app: Flask) -> None:
    """Background thread that refreshes every feed on an interval."""
    global _refresher_running
    interval = app.config["REFRESH_MINUTES"]
    if interval <= 0:
        return
    # Avoid double-start under the werkzeug reloader parent process.
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return
    with _refresher_started:
        if _refresher_running:
            return
        _refresher_running = True

    from .fetcher import refresh_all_feeds
    from .models import int_setting

    def loop():
        time.sleep(20)  # let the app finish booting first
        while True:
            # Admins can change the cadence at runtime; re-read it every cycle.
            with app.app_context():
                minutes = int_setting("refresh_minutes", app.config["REFRESH_MINUTES"])
            if minutes > 0:
                try:
                    refresh_all_feeds(app)
                except Exception:
                    logging.getLogger("hyprfeed").exception("background refresh failed")
            time.sleep(max(minutes, 1) * 60)

    threading.Thread(target=loop, daemon=True, name="hyprfeed-refresher").start()
