import threading
import xml.etree.ElementTree as ET

from flask import (Blueprint, Response, abort, current_app, jsonify,
                   render_template, request, url_for)
from flask_login import current_user, login_required
from sqlalchemy import func

from .auth import EMAIL_RE
from .fetcher import (_favicon_for, add_feed, create_scrape_feed,
                      google_news_fallback, refresh_feed, scrape_candidates)
from .models import (Entry, Feed, FeedGroup, Hidden, ReadMark, Star,
                     Subscription, User, db, int_setting, purge_feed,
                     set_setting, utcnow)


def retention_cap() -> int:
    return int_setting("max_entries_per_feed", current_app.config["MAX_ENTRIES_PER_FEED"])

bp = Blueprint("main", __name__)

VIEWS = ("magazine", "cards", "list")
FILTERS = ("all", "unread", "saved", "history")


def _subscribed_feed_ids():
    return [
        fid for (fid,) in db.session.query(Subscription.feed_id)
        .filter(Subscription.user_id == current_user.id)
    ]


def _hidden_sub():
    return db.session.query(Hidden.entry_id).filter(Hidden.user_id == current_user.id)


def _entries_query(feed_ids, filter_name):
    q = Entry.query.filter(Entry.feed_id.in_(feed_ids), Entry.id.not_in(_hidden_sub()))
    if filter_name == "unread":
        read = db.session.query(ReadMark.entry_id).filter(ReadMark.user_id == current_user.id)
        q = q.filter(Entry.id.not_in(read))
    elif filter_name == "saved":
        starred = db.session.query(Star.entry_id).filter(Star.user_id == current_user.id)
        q = q.filter(Entry.id.in_(starred))
    elif filter_name == "history":
        # Reading history: most recently read first.
        q = q.join(ReadMark, (ReadMark.entry_id == Entry.id)
                   & (ReadMark.user_id == current_user.id))
        return q.order_by(ReadMark.read_at.desc())
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
        .join(Feed)
        .order_by(func.coalesce(Subscription.position, 1_000_000), func.lower(Feed.title))
        .all()
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
            .filter(Entry.feed_id.in_(all_ids), Entry.id.not_in(read_sub),
                    Entry.id.not_in(_hidden_sub()))
            .group_by(Entry.feed_id).all()
        )
        unread_counts = dict(rows)

    groups = (
        FeedGroup.query.filter_by(user_id=current_user.id)
        .order_by(func.coalesce(FeedGroup.position, 1_000_000), func.lower(FeedGroup.name))
        .all()
    )
    group_members = {g.id: [s for s in subs if s.group_id == g.id] for g in groups}
    valid_group_ids = set(group_members)
    ungrouped = [s for s in subs if s.group_id not in valid_group_ids]

    # Sidebar top level: ungrouped site feeds and groups interleaved by the
    # shared position sequence.
    def _pos(obj):
        return obj.position if obj.position is not None else 1_000_000

    sidebar_items = sorted(
        [("group", g) for g in groups]
        + [("sub", s) for s in ungrouped if not s.feed.is_youtube],
        key=lambda pair: _pos(pair[1]),
    )

    return {
        "feed_titles": {s.feed_id: s.display_title for s in subs},
        "sidebar_items": sidebar_items,
        "site_subs": [s for s in ungrouped if not s.feed.is_youtube],
        "youtube_subs": [s for s in ungrouped if s.feed.is_youtube],
        "groups": groups,
        "group_members": group_members,
        "group_unread": {
            g.id: sum(unread_counts.get(s.feed_id, 0) for s in group_members[g.id])
            for g in groups
        },
        "manage_ungrouped": ungrouped,
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
        "inst_refresh": int_setting("refresh_minutes", current_app.config["REFRESH_MINUTES"]),
        "inst_retention": retention_cap(),
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


def _ago_label(dt) -> str:
    seconds = int((utcnow() - dt).total_seconds())
    if seconds < 60:
        return "now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    days = hours // 24
    if days < 7:
        return f"{days}d"
    return dt.strftime("%b %-d")


@bp.route("/search")
@login_required
def search():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify(feeds=[], entries=[])
    like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"

    subs = (
        Subscription.query.filter_by(user_id=current_user.id)
        .join(Feed)
        .order_by(func.coalesce(Subscription.position, 1_000_000), func.lower(Feed.title))
        .all()
    )
    q_lower = q.lower()
    feed_hits = [
        {"id": s.feed_id, "title": s.display_title, "icon": s.feed.icon_url}
        for s in subs if q_lower in s.display_title.lower()
    ][:5]

    feed_ids = [s.feed_id for s in subs]
    titles = {s.feed_id: s.display_title for s in subs}
    entries = []
    if feed_ids:
        from sqlalchemy import or_
        read_sub = db.session.query(ReadMark.entry_id).filter(ReadMark.user_id == current_user.id)
        rows = (
            Entry.query.filter(
                Entry.feed_id.in_(feed_ids),
                Entry.id.not_in(_hidden_sub()),
                or_(Entry.title.ilike(like, escape="\\"),
                    Entry.summary.ilike(like, escape="\\")),
            )
            .order_by(Entry.published.desc()).limit(20).all()
        )
        read_ids = {
            eid for (eid,) in read_sub.filter(ReadMark.entry_id.in_([r.id for r in rows]))
        } if rows else set()
        entries = [{
            "id": e.id,
            "title": e.title,
            "feed": titles.get(e.feed_id, ""),
            "icon": e.feed.icon_url,
            "ago": _ago_label(e.published),
            "read": e.id in read_ids,
        } for e in rows]
    return jsonify(feeds=feed_hits, entries=entries)


@bp.route("/feeds/add", methods=["POST"])
@login_required
def feeds_add():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify(error="Enter a website or feed address."), 400
    if data.get("scrape"):
        feed, error = create_scrape_feed(url, retention_cap())
    else:
        feed, error = add_feed(url)
    if error:
        # Whatever went wrong with the feed (none advertised, or advertised but
        # gated/dead like apnews.com's stale index.rss): if the page itself has
        # recognizable articles, offer to watch it instead.
        can_scrape = False
        google_news = None
        if not data.get("scrape"):
            candidates, _, _ = scrape_candidates(url)
            can_scrape = len(candidates) >= 3
            if not can_scrape and "blocks automated readers" in error:
                # Hard bot wall: offer the public Google News feed as a choice.
                google_news = google_news_fallback(url)
        return jsonify(error=error, can_scrape=can_scrape, google_news=google_news), 422
    existing = Subscription.query.filter_by(user_id=current_user.id, feed_id=feed.id).first()
    if existing:
        return jsonify(error="You already follow this feed."), 409
    max_pos = (
        db.session.query(func.max(Subscription.position))
        .filter(Subscription.user_id == current_user.id).scalar()
    )
    db.session.add(Subscription(
        user_id=current_user.id, feed_id=feed.id,
        position=0 if max_pos is None else max_pos + 1,
        custom_title=(data.get("custom_title") or "").strip()[:300] or None,
    ))
    db.session.commit()
    return jsonify(ok=True, redirect=url_for("main.index", feed=feed.id),
                   title=(data.get("custom_title") or "").strip() or feed.title or feed.url)


@bp.route("/feeds/export.opml")
@login_required
def feeds_export():
    subs = (
        Subscription.query.filter_by(user_id=current_user.id)
        .join(Feed)
        .order_by(func.coalesce(Subscription.position, 1_000_000), func.lower(Feed.title))
        .all()
    )
    opml = ET.Element("opml", version="2.0")
    head = ET.SubElement(opml, "head")
    ET.SubElement(head, "title").text = "Hyprfeed subscriptions"
    ET.SubElement(head, "dateCreated").text = utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
    body = ET.SubElement(opml, "body")
    for sub in subs:
        attrs = {
            "type": "rss",
            "text": sub.display_title,
            "title": sub.display_title,
            "xmlUrl": sub.feed.url,
        }
        if sub.feed.site_url:
            attrs["htmlUrl"] = sub.feed.site_url
        if sub.feed.kind == "scrape":
            # Round-trip marker so a Hyprfeed import restores the page watcher.
            attrs["hyprfeedKind"] = "scrape"
        ET.SubElement(body, "outline", attrs)
    xml = ET.tostring(opml, encoding="unicode", xml_declaration=True)
    return Response(xml, mimetype="text/x-opml",
                    headers={"Content-Disposition": "attachment; filename=hyprfeed.opml"})


def _refresh_feeds_async(app, feed_ids):
    def work():
        with app.app_context():
            from .models import int_setting as _int
            cap = _int("max_entries_per_feed", app.config["MAX_ENTRIES_PER_FEED"])
            for feed in Feed.query.filter(Feed.id.in_(feed_ids)):
                try:
                    refresh_feed(feed, cap)
                except Exception:
                    db.session.rollback()
    threading.Thread(target=work, daemon=True, name="hyprfeed-import-refresh").start()


@bp.route("/feeds/import", methods=["POST"])
@login_required
def feeds_import():
    upload = request.files.get("opml")
    if not upload:
        return jsonify(error="Choose an OPML file to import."), 400
    raw = upload.read(2_000_000)
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return jsonify(error="That file doesn't look like valid OPML."), 422

    outlines = [o for o in root.iter("outline") if o.get("xmlUrl")]
    if not outlines:
        return jsonify(error="No feeds found in that file."), 422
    outlines = outlines[:500]

    subscribed = set(_subscribed_feed_ids())
    max_pos = (
        db.session.query(func.max(Subscription.position))
        .filter(Subscription.user_id == current_user.id).scalar()
    )
    next_pos = 0 if max_pos is None else max_pos + 1

    added, skipped, new_feed_ids = 0, 0, []
    seen_urls = set()
    for outline in outlines:
        url = outline.get("xmlUrl", "").strip()[:500]
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        feed = Feed.query.filter_by(url=url).first()
        if feed is None:
            feed = Feed(
                url=url,
                kind="scrape" if outline.get("hyprfeedKind") == "scrape" else "rss",
                title=(outline.get("title") or outline.get("text") or "")[:300],
                site_url=(outline.get("htmlUrl") or "")[:500] or None,
                icon_url=_favicon_for(outline.get("htmlUrl") or url),
            )
            db.session.add(feed)
            db.session.flush()
            new_feed_ids.append(feed.id)
        if feed.id in subscribed:
            skipped += 1
            continue
        db.session.add(Subscription(user_id=current_user.id, feed_id=feed.id,
                                    position=next_pos))
        subscribed.add(feed.id)
        next_pos += 1
        added += 1
    db.session.commit()

    if new_feed_ids:
        # Fetch newly created feeds in the background so import stays instant.
        _refresh_feeds_async(current_app._get_current_object(), new_feed_ids)
    return jsonify(ok=True, added=added, skipped=skipped)


@bp.route("/groups", methods=["POST"])
@login_required
def group_create():
    name = ((request.get_json(silent=True) or {}).get("name") or "").strip()[:60]
    if not name:
        return jsonify(error="Give the group a name."), 400
    max_pos = (
        db.session.query(func.max(FeedGroup.position))
        .filter(FeedGroup.user_id == current_user.id).scalar()
    )
    group = FeedGroup(user_id=current_user.id, name=name,
                      position=0 if max_pos is None else max_pos + 1)
    db.session.add(group)
    db.session.commit()
    return jsonify(ok=True, id=group.id, name=group.name)


def _own_group(group_id) -> "FeedGroup":
    group = db.session.get(FeedGroup, group_id)
    if group is None or group.user_id != current_user.id:
        abort(404)
    return group


@bp.route("/groups/<int:group_id>/rename", methods=["POST"])
@login_required
def group_rename(group_id):
    group = _own_group(group_id)
    name = ((request.get_json(silent=True) or {}).get("name") or "").strip()[:60]
    if not name:
        return jsonify(error="Give the group a name."), 400
    group.name = name
    db.session.commit()
    return jsonify(ok=True, name=group.name)


@bp.route("/groups/<int:group_id>/delete", methods=["POST"])
@login_required
def group_delete(group_id):
    group = _own_group(group_id)
    Subscription.query.filter_by(user_id=current_user.id, group_id=group.id) \
        .update({"group_id": None}, synchronize_session=False)
    db.session.delete(group)
    db.session.commit()
    return jsonify(ok=True)


@bp.route("/groups/<int:group_id>/collapse", methods=["POST"])
@login_required
def group_collapse(group_id):
    group = _own_group(group_id)
    group.collapsed = bool((request.get_json(silent=True) or {}).get("collapsed"))
    db.session.commit()
    return jsonify(ok=True)


@bp.route("/feeds/organize", methods=["POST"])
@login_required
def feeds_organize():
    """Apply the settings drag layout: a flat sequence of group headers and
    feeds, where a feed belongs to the most recent group above it (or none)."""
    layout = (request.get_json(silent=True) or {}).get("layout") or []
    if not isinstance(layout, list):
        return jsonify(error="Bad layout payload."), 400
    subs = {s.feed_id: s for s in Subscription.query.filter_by(user_id=current_user.id)}
    groups = {g.id: g for g in FeedGroup.query.filter_by(user_id=current_user.id)}
    # One shared sequence for groups and feeds so the sidebar can interleave
    # groups between ungrouped feeds exactly as arranged.
    seq = 0
    for item in layout[:1000]:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "group":
            group = groups.get(item.get("id"))
            if group:
                group.position = seq
                seq += 1
        elif item.get("type") == "feed":
            sub = subs.get(item.get("id"))
            if sub:
                sub.position = seq
                seq += 1
                # Membership is explicit — containment in the UI, never
                # inferred from adjacency.
                gid = item.get("group")
                sub.group_id = gid if gid in groups else None
    db.session.commit()
    return jsonify(ok=True)


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
    title = (request.get_json(silent=True) or {}).get("title", "").strip()[:300]
    sub.custom_title = title or None
    db.session.commit()
    return jsonify(ok=True, title=sub.display_title)


@bp.route("/refresh", methods=["POST"])
@login_required
def refresh():
    new_total = 0
    for feed in Feed.query.filter(Feed.id.in_(_subscribed_feed_ids())):
        try:
            new_total += refresh_feed(feed, retention_cap())
        except Exception:
            db.session.rollback()
    return jsonify(ok=True, new=new_total)


@bp.route("/entries/<int:entry_id>")
@login_required
def entry_detail(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    if entry.feed_id not in _subscribed_feed_ids():
        abort(404)
    was_read = db.session.get(ReadMark, (current_user.id, entry.id)) is not None
    auto_marked = False
    if current_user.mark_read_on_open and not was_read:
        _set_read(entry.id, True)
        auto_marked = True
    sub = Subscription.query.filter_by(user_id=current_user.id, feed_id=entry.feed_id).first()
    return jsonify(
        id=entry.id,
        feed_id=entry.feed_id,
        read=was_read or auto_marked,
        auto_marked=auto_marked,
        title=entry.title,
        url=entry.url,
        author=entry.author,
        content=entry.content,
        image=entry.image_url,
        feed=sub.display_title if sub else entry.feed.title,
        feed_icon=entry.feed.icon_url,
        site_url=entry.feed.site_url,
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
    _set_read(entry_id, bool((request.get_json(silent=True) or {}).get("read", True)))
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


@bp.route("/entries/<int:entry_id>/hide", methods=["POST"])
@login_required
def entry_hide(entry_id):
    Entry.query.get_or_404(entry_id)
    hide = bool((request.get_json(silent=True) or {}).get("hidden", True))
    row = db.session.get(Hidden, (current_user.id, entry_id))
    if hide and not row:
        db.session.add(Hidden(user_id=current_user.id, entry_id=entry_id))
    elif not hide and row:
        db.session.delete(row)
    db.session.commit()
    return jsonify(ok=True, hidden=hide)


@bp.route("/entries/read-all", methods=["POST"])
@login_required
def read_all():
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
    if "name" in data:
        current_user.name = (data.get("name") or "").strip()[:120] or None
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


@bp.route("/admin/instance", methods=["POST"])
@login_required
def admin_instance():
    _require_admin()
    data = request.get_json(silent=True) or {}
    if "refresh_minutes" in data:
        try:
            minutes = int(data["refresh_minutes"])
        except (TypeError, ValueError):
            return jsonify(error="Refresh interval must be a number of minutes."), 400
        if not 0 <= minutes <= 1440:
            return jsonify(error="Refresh interval must be between 0 and 1440 minutes."), 400
        set_setting("refresh_minutes", str(minutes))
    if "max_entries_per_feed" in data:
        try:
            cap = int(data["max_entries_per_feed"])
        except (TypeError, ValueError):
            return jsonify(error="Stories per feed must be a number."), 400
        if not 20 <= cap <= 5000:
            return jsonify(error="Stories per feed must be between 20 and 5000."), 400
        set_setting("max_entries_per_feed", str(cap))
    return jsonify(ok=True)


@bp.route("/admin/registration", methods=["POST"])
@login_required
def admin_registration():
    _require_admin()
    open_ = bool((request.get_json(silent=True) or {}).get("open"))
    set_setting("registration_open", "1" if open_ else "0")
    return jsonify(ok=True, open=open_)


@bp.route("/admin/users", methods=["POST"])
@login_required
def admin_create_user():
    _require_admin()
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip().lower()
    password = data.get("password") or ""
    if len(username) > 80 or not EMAIL_RE.match(username):
        return jsonify(error="Enter a valid email address."), 400
    if len(password) < 8:
        return jsonify(error="Passwords need at least 8 characters."), 400
    if User.query.filter(func.lower(User.username) == username).first():
        return jsonify(error="An account with that email already exists."), 409
    user = User(username=username, is_admin=bool(data.get("is_admin")),
                name=(data.get("name") or "").strip()[:120] or None)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify(ok=True, id=user.id)


@bp.route("/admin/users/<int:user_id>/password", methods=["POST"])
@login_required
def admin_reset_password(user_id):
    _require_admin()
    user = User.query.get_or_404(user_id)
    new = (request.get_json(silent=True) or {}).get("new", "")
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
    Hidden.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    FeedGroup.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    db.session.delete(user)  # subscriptions cascade via the relationship
    db.session.flush()
    _gc_orphan_feeds()
    db.session.commit()
    return jsonify(ok=True)


@bp.route("/account/password", methods=["POST"])
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    current = data.get("current", "")
    new = data.get("new", "")
    if not current_user.check_password(current):
        return jsonify(error="Current password is wrong."), 403
    if len(new) < 8:
        return jsonify(error="New password needs at least 8 characters."), 400
    current_user.set_password(new)
    db.session.commit()
    return jsonify(ok=True)
