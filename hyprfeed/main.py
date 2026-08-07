from flask import (Blueprint, abort, current_app, jsonify, render_template,
                   request, url_for)
from flask_login import current_user, login_required
from sqlalchemy import func

from .fetcher import add_feed, create_scrape_feed, refresh_feed, scrape_candidates
from .models import (Entry, Feed, ReadMark, Star, Subscription, User, db,
                     purge_feed, set_setting, utcnow)

bp = Blueprint("main", __name__)

VIEWS = ("magazine", "cards", "list")
FILTERS = ("all", "unread", "saved")


def _subscribed_feed_ids():
    return [
        fid for (fid,) in db.session.query(Subscription.feed_id)
        .filter(Subscription.user_id == current_user.id)
    ]


def _entries_query(feed_ids, filter_name):
    q = Entry.query.filter(Entry.feed_id.in_(feed_ids))
    if filter_name == "unread":
        read = db.session.query(ReadMark.entry_id).filter(ReadMark.user_id == current_user.id)
        q = q.filter(Entry.id.not_in(read))
    elif filter_name == "saved":
        starred = db.session.query(Star.entry_id).filter(Star.user_id == current_user.id)
        q = q.filter(Entry.id.in_(starred))
    return q.order_by(Entry.published.desc())


def _page_context():
    view = request.args.get("view", current_user.view_mode)
    if view not in VIEWS:
        view = "magazine"
    filter_name = request.args.get("filter", "all")
    if filter_name not in FILTERS:
        filter_name = "all"
    feed_id = request.args.get("feed", type=int)
    page = max(request.args.get("page", 1, type=int), 1)

    # Switching views from the UI persists the choice.
    if request.args.get("view") and view != current_user.view_mode:
        current_user.view_mode = view
        db.session.commit()

    subs = (
        Subscription.query.filter_by(user_id=current_user.id)
        .join(Feed).order_by(func.lower(Feed.title)).all()
    )
    feed_ids = [s.feed_id for s in subs]
    active_sub = None
    if feed_id:
        active_sub = next((s for s in subs if s.feed_id == feed_id), None)
        if not active_sub:
            abort(404)
        feed_ids = [feed_id]

    per_page = current_app.config["ENTRIES_PER_PAGE"]
    query = _entries_query(feed_ids, filter_name) if feed_ids else None
    entries = (
        query.offset((page - 1) * per_page).limit(per_page + 1).all() if query else []
    )
    has_more = len(entries) > per_page
    entries = entries[:per_page]

    entry_ids = [e.id for e in entries]
    read_ids = {
        eid for (eid,) in db.session.query(ReadMark.entry_id)
        .filter(ReadMark.user_id == current_user.id, ReadMark.entry_id.in_(entry_ids))
    } if entry_ids else set()
    star_ids = {
        eid for (eid,) in db.session.query(Star.entry_id)
        .filter(Star.user_id == current_user.id, Star.entry_id.in_(entry_ids))
    } if entry_ids else set()

    # Per-feed unread counts for the sidebar.
    all_ids = [s.feed_id for s in subs]
    unread_counts = {}
    if all_ids:
        read_sub = db.session.query(ReadMark.entry_id).filter(ReadMark.user_id == current_user.id)
        rows = (
            db.session.query(Entry.feed_id, func.count(Entry.id))
            .filter(Entry.feed_id.in_(all_ids), Entry.id.not_in(read_sub))
            .group_by(Entry.feed_id).all()
        )
        unread_counts = dict(rows)

    return {
        "feed_titles": {s.feed_id: s.display_title for s in subs},
        "view": view,
        "filter": filter_name,
        "active_sub": active_sub,
        "subs": subs,
        "entries": entries,
        "read_ids": read_ids,
        "star_ids": star_ids,
        "unread_counts": unread_counts,
        "total_unread": sum(unread_counts.values()),
        "page": page,
        "has_more": has_more,
    }


def _admin_context():
    users = User.query.order_by(User.created_at).all()
    sub_counts = dict(
        db.session.query(Subscription.user_id, func.count()).group_by(Subscription.user_id)
    )
    return {
        "admin_users": users,
        "admin_sub_counts": sub_counts,
        "admin_stats": {
            "users": len(users),
            "feeds": db.session.query(func.count(Feed.id)).scalar(),
            "entries": db.session.query(func.count(Entry.id)).scalar(),
        },
    }


@bp.route("/")
@login_required
def index():
    ctx = _page_context()
    if request.args.get("partial"):
        return render_template("partials/entries.html", **ctx)
    if current_user.is_admin:
        ctx.update(_admin_context())
    return render_template("app.html", **ctx)


@bp.route("/feeds/add", methods=["POST"])
@login_required
def feeds_add():
    data = request.json or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify(error="Enter a website or feed address."), 400
    if data.get("scrape"):
        feed, error = create_scrape_feed(url, current_app.config["MAX_ENTRIES_PER_FEED"])
    else:
        feed, error = add_feed(url)
    if error:
        # No feed — but if the page has recognizable articles, offer to watch it.
        can_scrape = False
        if not data.get("scrape") and "no RSS or Atom feed" in error:
            candidates, _, _ = scrape_candidates(url)
            can_scrape = len(candidates) >= 3
        return jsonify(error=error, can_scrape=can_scrape), 422
    existing = Subscription.query.filter_by(user_id=current_user.id, feed_id=feed.id).first()
    if existing:
        return jsonify(error="You already follow this feed."), 409
    db.session.add(Subscription(user_id=current_user.id, feed_id=feed.id))
    db.session.commit()
    return jsonify(ok=True, redirect=url_for("main.index", feed=feed.id))


@bp.route("/feeds/<int:feed_id>/unsubscribe", methods=["POST"])
@login_required
def feeds_unsubscribe(feed_id):
    sub = Subscription.query.filter_by(user_id=current_user.id, feed_id=feed_id).first_or_404()
    db.session.delete(sub)
    db.session.flush()
    feed = db.session.get(Feed, feed_id)
    if feed and not feed.subscriptions.count():
        purge_feed(feed)  # nobody follows it anymore; drop entries and marks too
    db.session.commit()
    return jsonify(ok=True)


@bp.route("/feeds/<int:feed_id>/rename", methods=["POST"])
@login_required
def feeds_rename(feed_id):
    sub = Subscription.query.filter_by(user_id=current_user.id, feed_id=feed_id).first_or_404()
    title = (request.json or {}).get("title", "").strip()[:300]
    sub.custom_title = title or None
    db.session.commit()
    return jsonify(ok=True, title=sub.display_title)


@bp.route("/refresh", methods=["POST"])
@login_required
def refresh():
    new_total = 0
    for feed in Feed.query.filter(Feed.id.in_(_subscribed_feed_ids())):
        try:
            new_total += refresh_feed(feed, current_app.config["MAX_ENTRIES_PER_FEED"])
        except Exception:
            db.session.rollback()
    return jsonify(ok=True, new=new_total)


@bp.route("/entries/<int:entry_id>")
@login_required
def entry_detail(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    if entry.feed_id not in _subscribed_feed_ids():
        abort(404)
    if current_user.mark_read_on_open:
        _set_read(entry.id, True)
    sub = Subscription.query.filter_by(user_id=current_user.id, feed_id=entry.feed_id).first()
    return jsonify(
        id=entry.id,
        title=entry.title,
        url=entry.url,
        author=entry.author,
        content=entry.content,
        image=entry.image_url,
        feed=sub.display_title if sub else entry.feed.title,
        feed_icon=entry.feed.icon_url,
        published=entry.published.strftime("%B %-d, %Y · %H:%M"),
        minutes=max(1, round(entry.word_count / 220)) if entry.word_count else None,
        starred=entry.id in {
            eid for (eid,) in db.session.query(Star.entry_id)
            .filter(Star.user_id == current_user.id, Star.entry_id == entry.id)
        },
    )


def _set_read(entry_id: int, read: bool) -> None:
    mark = db.session.get(ReadMark, (current_user.id, entry_id))
    if read and not mark:
        db.session.add(ReadMark(user_id=current_user.id, entry_id=entry_id))
    elif not read and mark:
        db.session.delete(mark)
    db.session.commit()


@bp.route("/entries/<int:entry_id>/read", methods=["POST"])
@login_required
def entry_read(entry_id):
    Entry.query.get_or_404(entry_id)
    _set_read(entry_id, bool((request.json or {}).get("read", True)))
    return jsonify(ok=True)


@bp.route("/entries/<int:entry_id>/star", methods=["POST"])
@login_required
def entry_star(entry_id):
    Entry.query.get_or_404(entry_id)
    star = db.session.get(Star, (current_user.id, entry_id))
    if star:
        db.session.delete(star)
        starred = False
    else:
        db.session.add(Star(user_id=current_user.id, entry_id=entry_id))
        starred = True
    db.session.commit()
    return jsonify(ok=True, starred=starred)


@bp.route("/entries/read-all", methods=["POST"])
@login_required
def read_all():
    data = request.json or {}
    feed_id = data.get("feed")
    feed_ids = [feed_id] if feed_id else _subscribed_feed_ids()
    feed_ids = [f for f in feed_ids if f in _subscribed_feed_ids()]
    read_sub = db.session.query(ReadMark.entry_id).filter(ReadMark.user_id == current_user.id)
    unread = db.session.query(Entry.id).filter(
        Entry.feed_id.in_(feed_ids), Entry.id.not_in(read_sub)
    )
    now = utcnow()
    db.session.bulk_save_objects([
        ReadMark(user_id=current_user.id, entry_id=eid, read_at=now) for (eid,) in unread
    ])
    db.session.commit()
    return jsonify(ok=True)


@bp.route("/settings", methods=["POST"])
@login_required
def settings():
    data = request.json or {}
    if data.get("theme") in ("system", "light", "dark"):
        current_user.theme = data["theme"]
    if data.get("view_mode") in VIEWS:
        current_user.view_mode = data["view_mode"]
    if "mark_read_on_open" in data:
        current_user.mark_read_on_open = bool(data["mark_read_on_open"])
    db.session.commit()
    return jsonify(ok=True)


# ———— Admin ————

def _require_admin() -> None:
    if not current_user.is_admin:
        abort(403)


def _gc_orphan_feeds() -> None:
    """Drop feeds nobody subscribes to anymore (entries cascade)."""
    orphans = Feed.query.filter(
        Feed.id.not_in(db.session.query(Subscription.feed_id))
    ).all()
    for feed in orphans:
        purge_feed(feed)


@bp.route("/admin/registration", methods=["POST"])
@login_required
def admin_registration():
    _require_admin()
    open_ = bool((request.json or {}).get("open"))
    set_setting("registration_open", "1" if open_ else "0")
    return jsonify(ok=True, open=open_)


@bp.route("/admin/users/<int:user_id>/password", methods=["POST"])
@login_required
def admin_reset_password(user_id):
    _require_admin()
    user = User.query.get_or_404(user_id)
    new = (request.json or {}).get("new", "")
    if len(new) < 8:
        return jsonify(error="Passwords need at least 8 characters."), 400
    user.set_password(new)
    db.session.commit()
    return jsonify(ok=True)


@bp.route("/admin/users/<int:user_id>/toggle-admin", methods=["POST"])
@login_required
def admin_toggle_admin(user_id):
    _require_admin()
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify(error="You can't change your own admin status."), 400
    user.is_admin = not user.is_admin
    db.session.commit()
    return jsonify(ok=True, is_admin=user.is_admin)


@bp.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required
def admin_delete_user(user_id):
    _require_admin()
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify(error="You can't delete your own account from here."), 400
    ReadMark.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    Star.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    db.session.delete(user)  # subscriptions cascade via the relationship
    db.session.flush()
    _gc_orphan_feeds()
    db.session.commit()
    return jsonify(ok=True)


@bp.route("/account/password", methods=["POST"])
@login_required
def change_password():
    data = request.json or {}
    current = data.get("current", "")
    new = data.get("new", "")
    if not current_user.check_password(current):
        return jsonify(error="Current password is wrong."), 403
    if len(new) < 8:
        return jsonify(error="New password needs at least 8 characters."), 400
    current_user.set_password(new)
    db.session.commit()
    return jsonify(ok=True)
