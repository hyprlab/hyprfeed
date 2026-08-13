from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120))
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    theme = db.Column(db.String(10), default="system", nullable=False)  # system|light|dark
    view_mode = db.Column(db.String(10), default="magazine", nullable=False)  # magazine|cards|list
    mark_read_on_open = db.Column(db.Boolean, default=True, nullable=False)
    infinite_scroll = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    subscriptions = db.relationship(
        "Subscription", backref="user", cascade="all, delete-orphan", lazy="dynamic"
    )

    @property
    def display_name(self) -> str:
        return self.name or self.username

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Setting(db.Model):
    """Instance-wide key/value settings editable from the admin panel."""
    __tablename__ = "settings"

    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(500), nullable=False)


def get_setting(key: str) -> str | None:
    row = db.session.get(Setting, key)
    return row.value if row else None


def int_setting(key: str, fallback: int) -> int:
    """Admin-editable integer setting; the env-derived config value is the
    default until an admin saves one."""
    raw = get_setting(key)
    if raw is not None:
        try:
            return int(raw)
        except ValueError:
            pass
    return fallback


def set_setting(key: str, value: str) -> None:
    row = db.session.get(Setting, key)
    if row:
        row.value = value
    else:
        db.session.add(Setting(key=key, value=value))
    db.session.commit()


class Feed(db.Model):
    __tablename__ = "feeds"

    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500), unique=True, nullable=False, index=True)
    kind = db.Column(db.String(10), default="rss", nullable=False)  # rss|scrape
    site_url = db.Column(db.String(500))
    title = db.Column(db.String(300), default="", nullable=False)
    description = db.Column(db.Text, default="")
    icon_url = db.Column(db.String(500))
    etag = db.Column(db.String(300))
    last_modified = db.Column(db.String(120))
    last_fetched = db.Column(db.DateTime)
    last_error = db.Column(db.String(300))

    @property
    def is_youtube(self) -> bool:
        return "youtube.com/feeds/videos.xml" in (self.url or "")

    entries = db.relationship(
        "Entry", backref="feed", cascade="all, delete-orphan", lazy="dynamic"
    )
    subscriptions = db.relationship(
        "Subscription", backref="feed", cascade="all, delete-orphan", lazy="dynamic"
    )


class FeedGroup(db.Model):
    __tablename__ = "feed_groups"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(60), nullable=False)
    position = db.Column(db.Integer)
    collapsed = db.Column(db.Boolean, default=False, nullable=False)


class Subscription(db.Model):
    __tablename__ = "subscriptions"
    __table_args__ = (db.UniqueConstraint("user_id", "feed_id"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    feed_id = db.Column(db.Integer, db.ForeignKey("feeds.id"), nullable=False, index=True)
    group_id = db.Column(db.Integer, db.ForeignKey("feed_groups.id"))
    custom_title = db.Column(db.String(300))
    position = db.Column(db.Integer)  # per-user sidebar order
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    @property
    def display_title(self) -> str:
        return self.custom_title or self.feed.title or self.feed.url


class Entry(db.Model):
    __tablename__ = "entries"
    __table_args__ = (
        db.UniqueConstraint("feed_id", "guid"),
        db.Index("ix_entries_feed_published", "feed_id", "published"),
    )

    id = db.Column(db.Integer, primary_key=True)
    feed_id = db.Column(db.Integer, db.ForeignKey("feeds.id"), nullable=False)
    guid = db.Column(db.String(500), nullable=False)
    title = db.Column(db.String(500), default="Untitled", nullable=False)
    url = db.Column(db.String(1000))
    author = db.Column(db.String(200))
    summary = db.Column(db.Text, default="")  # plain-text snippet
    content = db.Column(db.Text, default="")  # sanitized HTML
    image_url = db.Column(db.String(1000))
    published = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    word_count = db.Column(db.Integer, default=0, nullable=False)


def purge_feed(feed: "Feed") -> None:
    """Delete a feed along with its entries AND their read/star marks —
    plain cascade would leave the marks orphaned."""
    entry_ids = db.session.query(Entry.id).filter(Entry.feed_id == feed.id)
    ReadMark.query.filter(ReadMark.entry_id.in_(entry_ids)).delete(synchronize_session=False)
    Star.query.filter(Star.entry_id.in_(entry_ids)).delete(synchronize_session=False)
    Hidden.query.filter(Hidden.entry_id.in_(entry_ids)).delete(synchronize_session=False)
    db.session.delete(feed)


class ReadMark(db.Model):
    __tablename__ = "read_marks"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey("entries.id"), primary_key=True)
    read_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class Star(db.Model):
    __tablename__ = "stars"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey("entries.id"), primary_key=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class Hidden(db.Model):
    __tablename__ = "hidden_entries"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey("entries.id"), primary_key=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
