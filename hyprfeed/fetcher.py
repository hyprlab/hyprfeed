"""Feed discovery, fetching and ingestion — plus a page watcher that
synthesizes a feed for sites that don't publish one."""
import logging
import re
import time
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .models import Entry, Feed, Hidden, ReadMark, Star, db, purge_feed, utcnow
from .sanitize import first_image, sanitize_html, strip_tags

log = logging.getLogger("hyprfeed.fetcher")

USER_AGENT = "Hyprfeed/1.0 (+https://github.com/hyprlab/hyprfeed) feed reader"
# Fallback for sites whose CDN/bot filter rejects unknown user agents.
BROWSER_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
TIMEOUT = 15
CONNECT_TIMEOUT = 6.05
COMMON_FEED_PATHS = ("feed", "rss", "atom.xml", "feed.xml", "rss.xml", "index.xml", "feed/")

# Shared session: connection pooling plus automatic retries so a transient
# DNS/connect/read blip or edge 5xx doesn't surface as "no feed found" —
# users reported first-try failures that succeeded on manual retry.
_session = requests.Session()
_adapter = HTTPAdapter(max_retries=Retry(
    total=2, connect=2, read=1, backoff_factor=0.4,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset(["GET", "HEAD"]),
    raise_on_status=False,
), pool_maxsize=10)
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)

_LINK_REL = re.compile(
    r"<link[^>]+(?:type=[\"']application/(?:rss|atom)\+xml[\"'][^>]*|rel=[\"']alternate[\"'][^>]*)>",
    re.I,
)
_HREF = re.compile(r"href=[\"']([^\"']+)[\"']", re.I)
_TYPE_OK = re.compile(r"type=[\"']application/(?:rss|atom)\+xml[\"']", re.I)


def _get(url: str, **kwargs) -> requests.Response:
    headers = {"User-Agent": USER_AGENT, **kwargs.pop("headers", {})}
    resp = _session.get(url, headers=headers, timeout=(CONNECT_TIMEOUT, TIMEOUT),
                        allow_redirects=True, **kwargs)
    if resp.status_code in (401, 403, 406, 429):
        headers["User-Agent"] = BROWSER_UA
        resp = _session.get(url, headers=headers, timeout=(CONNECT_TIMEOUT, TIMEOUT),
                            allow_redirects=True, **kwargs)
    return resp


def _looks_like_feed(content: bytes) -> bool:
    head = content[:2000].lstrip().lower()
    return any(marker in head for marker in (b"<rss", b"<feed", b"<rdf", b"<?xml"))


def google_news_fallback(url: str) -> dict | None:
    """Public Google News RSS scoped to a site — the legitimate way to follow
    publishers that block automated readers outright (e.g. Reuters)."""
    if not urlparse(url).scheme:
        url = "https://" + url
    domain = urlparse(url).netloc.replace("www.", "")
    if not domain or "." not in domain:
        return None
    from urllib.parse import quote
    return {
        "url": ("https://news.google.com/rss/search?q=site:" + quote(domain)
                + "&hl=en-US&gl=US&ceid=US:en"),
        "domain": domain,
        "title": f"{domain.split('.')[0].capitalize()} (via Google News)",
    }


def discover_feed_url(url: str) -> tuple[str | None, str | None]:
    """Resolve a website or feed URL to an actual feed URL.
    Returns (feed_url, error) — exactly one is set."""
    if not urlparse(url).scheme:
        url = "https://" + url
    try:
        resp = _get(url)
    except requests.RequestException as exc:
        reason = type(exc).__name__.replace("ConnectionError", "connection failed") \
            .replace("ConnectTimeout", "timed out").replace("ReadTimeout", "timed out")
        return None, f"Couldn't reach that site ({reason}). Check the address and try again."
    if resp.status_code in (401, 403):
        return None, ("That site blocks automated readers "
                      f"(HTTP {resp.status_code}). If it offers RSS, try the feed's direct URL.")
    if not resp.ok:
        return None, f"That site answered with HTTP {resp.status_code}."
    if _looks_like_feed(resp.content):
        return resp.url, None

    # It's an HTML page: look for <link rel="alternate" type="application/rss+xml">.
    html = resp.text[:200_000]
    for link_tag in _LINK_REL.findall(html):
        if not _TYPE_OK.search(link_tag):
            continue
        href = _HREF.search(link_tag)
        if href:
            return urljoin(resp.url, href.group(1)), None

    # Fall back to common feed locations.
    for path in COMMON_FEED_PATHS:
        candidate = urljoin(resp.url.rstrip("/") + "/", path)
        try:
            r = _get(candidate)
            if r.ok and _looks_like_feed(r.content):
                return r.url, None
        except requests.RequestException:
            continue
    return None, "Reached the site, but no RSS or Atom feed was advertised. Try the feed's direct URL."


def _entry_published(parsed_entry) -> datetime:
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        value = getattr(parsed_entry, attr, None)
        if value:
            try:
                return datetime.fromtimestamp(time.mktime(value))
            except (ValueError, OverflowError):
                continue
    return utcnow()


def _entry_image(parsed_entry, html_content: str) -> str | None:
    for media in getattr(parsed_entry, "media_thumbnail", []) or []:
        if media.get("url"):
            return media["url"]
    for media in getattr(parsed_entry, "media_content", []) or []:
        if media.get("url") and media.get("medium", "image") == "image":
            return media["url"]
    for enc in getattr(parsed_entry, "enclosures", []) or []:
        if enc.get("href") and enc.get("type", "").startswith("image/"):
            return enc["href"]
    return first_image(html_content)


def _entry_content(parsed_entry) -> str:
    # Some feeds (e.g. Tom's Hardware) ship multiple content blocks where the
    # first is an author bio and a later one is the article — take the longest.
    candidates = [
        item.get("value") or ""
        for item in (getattr(parsed_entry, "content", None) or [])
    ]
    best = max(candidates, key=len, default="")
    return best or getattr(parsed_entry, "summary", "") or ""


_URL_IN_TEXT = re.compile(r"https?://\S+")
_EMPTY_LABEL = re.compile(r"(?:Article|Comments) URL:\s*", re.I)


def _snippet(text: str) -> str:
    """Human-readable summary snippet: bare URLs and link-label boilerplate
    (as in Hacker News feeds) are noise at card size."""
    text = _URL_IN_TEXT.sub("", text)
    text = _EMPTY_LABEL.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()[:400]
    return text if len(text) >= 5 else ""


def _favicon_for(site_url: str) -> str | None:
    domain = urlparse(site_url).netloc
    if not domain:
        return None
    return f"https://icons.duckduckgo.com/ip3/{domain}.ico"


def _prune_entries(feed_id: int, max_entries: int) -> None:
    """Trim a feed to its newest max_entries, removing read/star marks of the
    pruned entries so they don't accumulate as orphans."""
    ids_to_keep = [
        eid for (eid,) in db.session.query(Entry.id)
        .filter(Entry.feed_id == feed_id)
        .order_by(Entry.published.desc())
        .limit(max_entries)
    ]
    if len(ids_to_keep) < max_entries:
        return
    doomed = db.session.query(Entry.id).filter(
        Entry.feed_id == feed_id, Entry.id.not_in(ids_to_keep)
    )
    ReadMark.query.filter(ReadMark.entry_id.in_(doomed)).delete(synchronize_session=False)
    Star.query.filter(Star.entry_id.in_(doomed)).delete(synchronize_session=False)
    Hidden.query.filter(Hidden.entry_id.in_(doomed)).delete(synchronize_session=False)
    db.session.query(Entry).filter(
        Entry.feed_id == feed_id, Entry.id.not_in(ids_to_keep)
    ).delete(synchronize_session=False)


# ———— Page watcher (sites without feeds) ————

# Path segments that mark navigation/utility pages, never articles.
NOISE_SEGMENTS = {
    "author", "authors", "tag", "tags", "category", "categories", "topic",
    "topics", "page", "about", "contact", "donate", "subscribe", "membership",
    "login", "register", "signup", "signin", "search", "privacy", "terms",
    "faq", "team", "careers", "jobs", "advertise", "newsletter", "shop",
    "store", "cart", "account", "issues", "events", "press", "legal",
    "cookies", "sitemap", "wp-content", "static",
}

_ANCHOR = re.compile(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.I | re.S)


def extract_article_links(html: str, base_url: str, limit: int = 30) -> list[tuple[str, str]]:
    """Heuristically pick article links out of a listing page: same-site links
    with slug-like paths and headline-length anchor text, in page order."""
    host = urlparse(base_url).netloc.replace("www.", "")
    found: dict[str, str] = {}
    for href, inner in _ANCHOR.findall(html[:500_000]):
        parsed = urlparse(urljoin(base_url, href.strip()))
        if parsed.scheme not in ("http", "https"):
            continue
        if parsed.netloc.replace("www.", "") != host:
            continue
        # Canonical article URL: no query (tracking params like ?hsLang=en
        # would duplicate entries) and no fragment.
        url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        segments = [s for s in parsed.path.split("/") if s]
        if not segments:
            continue
        if any(s.lower() in NOISE_SEGMENTS for s in segments):
            continue
        # Article paths end in a wordy slug (or a dated path like /2026/08/06/x).
        if "-" not in segments[-1] and not any(s.isdigit() for s in segments):
            continue
        text = unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", inner))).strip()
        if len(text.split()) < 4 or len(text) < 20:
            continue
        if url not in found or len(text) > len(found[url]):
            found[url] = text
        if len(found) >= limit * 2:
            break
    return list(found.items())[:limit]


def _meta_content(html: str, *keys: str) -> str | None:
    wanted = {k.lower() for k in keys}
    # Quote-aware: an apostrophe inside "…" (or a " inside '…') must not
    # truncate the value.
    key_re = re.compile(r"(?:property|name)=(?:\"([^\"]+)\"|'([^']+)')", re.I)
    content_re = re.compile(r"content=(?:\"([^\"]*)\"|'([^']*)')", re.I)
    for m in re.finditer(r"<meta\b[^>]*>", html[:300_000], re.I):
        tag = m.group(0)
        key = key_re.search(tag)
        if not key or (key.group(1) or key.group(2)).lower() not in wanted:
            continue
        content = content_re.search(tag)
        if content:
            value = (content.group(1) or content.group(2) or "").strip()
            if value:
                return unescape(value)
    return None


def _parse_iso_date(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    dt = None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:  # RFC 2822 ("Thu, 07 Aug 2026 12:30:00 GMT") shows up in meta tags too
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


_JSONLD_DATE = re.compile(r'"datePublished"\s*:\s*"([^"]+)"')
_TIME_TAG = re.compile(r"<time\b[^>]+datetime=[\"']([^\"']+)[\"']", re.I)
_URL_DATE = re.compile(r"/(20\d{2})/(\d{1,2})/(\d{1,2})(?:/|$)")


def _published_from_page(html: str, url: str) -> datetime | None:
    """Best-effort publish date, most reliable source first."""
    candidates = [
        _meta_content(html, "article:published_time", "og:article:published_time",
                      "article:published", "datepublished", "parsely-pub-date",
                      "sailthru.date", "dc.date", "dc.date.issued", "date",
                      "pubdate", "publish-date", "publication_date"),
    ]
    jsonld = _JSONLD_DATE.search(html[:400_000])
    if jsonld:
        candidates.insert(0, jsonld.group(1))
    time_tag = _TIME_TAG.search(html[:400_000])
    if time_tag:
        candidates.append(time_tag.group(1))
    for value in candidates:
        parsed = _parse_iso_date(value)
        if parsed:
            return parsed
    url_date = _URL_DATE.search(urlparse(url).path)
    if url_date:
        try:
            return datetime(int(url_date.group(1)), int(url_date.group(2)),
                            int(url_date.group(3)))
        except ValueError:
            pass
    return None


def _page_title(html: str) -> str | None:
    m = re.search(r"<title[^>]*>(.*?)</title>", html[:100_000], re.I | re.S)
    if m:
        return unescape(re.sub(r"\s+", " ", m.group(1))).strip() or None
    return None


def _article_metadata(url: str) -> dict:
    """Best-effort og:/meta scrape of one article page."""
    try:
        resp = _get(url)
        if not resp.ok:
            return {}
    except requests.RequestException:
        return {}
    html = resp.text
    return {
        "title": _meta_content(html, "og:title", "twitter:title") or _page_title(html),
        "description": _meta_content(html, "og:description", "twitter:description", "description"),
        "image": _meta_content(html, "og:image", "twitter:image"),
        "author": _meta_content(html, "author", "article:author"),
        "published": _published_from_page(html, url),
    }


def _refresh_scrape(feed: Feed, max_entries: int, max_new_fetches: int = 8) -> int:
    """Refresh a page-watcher feed: re-scan the listing page, ingest new links."""
    headers = {}
    if feed.etag:
        headers["If-None-Match"] = feed.etag
    if feed.last_modified:
        headers["If-Modified-Since"] = feed.last_modified
    try:
        resp = _get(feed.url, headers=headers)
    except requests.RequestException as exc:
        feed.last_error = str(exc)[:300]
        feed.last_fetched = utcnow()
        db.session.commit()
        return 0

    feed.last_fetched = utcnow()
    if resp.status_code == 304:
        feed.last_error = None
        db.session.commit()
        return 0
    if not resp.ok:
        feed.last_error = f"HTTP {resp.status_code}"
        db.session.commit()
        return 0

    feed.etag = resp.headers.get("ETag")
    feed.last_modified = resp.headers.get("Last-Modified")

    candidates = extract_article_links(resp.text, resp.url)
    if not candidates:
        feed.last_error = "No article links found on the page"
        db.session.commit()
        return 0
    feed.last_error = None

    existing_guids = {
        guid for (guid,) in db.session.query(Entry.guid).filter(Entry.feed_id == feed.id)
    }
    new_count = 0
    for url, anchor_text in candidates:
        guid = url[:500]
        if guid in existing_guids:
            continue
        if new_count >= max_new_fetches:
            break  # remaining new links get picked up on the next refresh
        meta = _article_metadata(url)
        description = meta.get("description") or ""
        entry = Entry(
            feed_id=feed.id,
            guid=guid,
            title=(meta.get("title") or anchor_text)[:500],
            url=url,
            author=(meta.get("author") or "")[:200] or None,
            summary=_snippet(description),
            content=sanitize_html(f"<p>{description}</p>") if description else "",
            image_url=(meta.get("image") or "")[:1000] or None,
            published=min(meta.get("published") or utcnow(), utcnow()),
            word_count=0,
        )
        db.session.add(entry)
        existing_guids.add(guid)
        new_count += 1

    db.session.flush()
    _prune_entries(feed.id, max_entries)
    db.session.commit()
    return new_count


def scrape_candidates(url: str) -> tuple[list[tuple[str, str]], str, "requests.Response | None"]:
    """Fetch a page and return (article candidates, error, response)."""
    if not urlparse(url).scheme:
        url = "https://" + url
    try:
        resp = _get(url)
    except requests.RequestException:
        return [], "Couldn't reach that site.", None
    if not resp.ok:
        return [], f"That site answered with HTTP {resp.status_code}.", None
    return extract_article_links(resp.text, resp.url), "", resp


def create_scrape_feed(url: str, max_entries: int = 300) -> tuple[Feed | None, str | None]:
    """Create (or reuse) a page-watcher feed for a site without RSS."""
    candidates, error, resp = scrape_candidates(url)
    if error:
        return None, error
    if len(candidates) < 3:
        return None, "Couldn't find article links on that page to watch."
    page_url = resp.url.rstrip("/")
    feed = Feed.query.filter_by(url=page_url).first()
    if feed:
        return feed, None
    html = resp.text
    site_title = (_meta_content(html, "og:site_name") or _page_title(html)
                  or urlparse(page_url).netloc)
    # "Home ❧ Current Affairs" -> "Current Affairs"
    site_title = re.sub(r"^(?:home|welcome)\s*[|\-–—·:❧»]\s*", "", site_title, flags=re.I)
    feed = Feed(
        url=page_url,
        kind="scrape",
        site_url=page_url,
        title=site_title[:300],
        description=(_meta_content(html, "description", "og:description") or "")[:1000],
        icon_url=_favicon_for(page_url),
    )
    db.session.add(feed)
    db.session.flush()
    _refresh_scrape(feed, max_entries=max_entries, max_new_fetches=12)
    if not feed.entries.count():
        purge_feed(feed)
        db.session.commit()
        return None, "Found the page but couldn't read any articles from it."
    return feed, None


def refresh_feed(feed: Feed, max_entries: int = 300) -> int:
    """Fetch a feed and ingest new entries. Returns count of new entries."""
    if feed.kind == "scrape":
        return _refresh_scrape(feed, max_entries)
    headers = {}
    if feed.etag:
        headers["If-None-Match"] = feed.etag
    if feed.last_modified:
        headers["If-Modified-Since"] = feed.last_modified

    try:
        resp = _get(feed.url, headers=headers)
    except requests.RequestException as exc:
        feed.last_error = str(exc)[:300]
        feed.last_fetched = utcnow()
        db.session.commit()
        return 0

    feed.last_fetched = utcnow()
    if resp.status_code == 304:
        feed.last_error = None
        db.session.commit()
        return 0
    if not resp.ok:
        feed.last_error = f"HTTP {resp.status_code}"
        db.session.commit()
        return 0

    parsed = feedparser.parse(resp.content)
    if parsed.bozo and not parsed.entries:
        feed.last_error = "Could not parse feed"
        db.session.commit()
        return 0

    feed.etag = resp.headers.get("ETag")
    feed.last_modified = resp.headers.get("Last-Modified")
    feed.last_error = None

    feed_info = parsed.feed
    if not feed.title:
        feed.title = strip_tags(feed_info.get("title", ""))[:300] or urlparse(feed.url).netloc
    if not feed.site_url:
        feed.site_url = feed_info.get("link") or feed.url
    if not feed.description:
        feed.description = strip_tags(feed_info.get("subtitle", ""))[:1000]
    if not feed.icon_url:
        feed.icon_url = _favicon_for(feed.site_url or feed.url)

    existing_guids = {
        guid for (guid,) in db.session.query(Entry.guid).filter(Entry.feed_id == feed.id)
    }
    new_count = 0
    for parsed_entry in parsed.entries[:max_entries]:
        guid = (getattr(parsed_entry, "id", None) or getattr(parsed_entry, "link", None)
                or getattr(parsed_entry, "title", ""))[:500]
        if not guid or guid in existing_guids:
            continue
        raw_content = _entry_content(parsed_entry)
        content = sanitize_html(raw_content)
        text = strip_tags(raw_content)
        entry = Entry(
            feed_id=feed.id,
            guid=guid,
            title=strip_tags(getattr(parsed_entry, "title", ""))[:500] or "Untitled",
            url=getattr(parsed_entry, "link", None),
            author=strip_tags(getattr(parsed_entry, "author", ""))[:200] or None,
            summary=_snippet(text),
            content=content,
            image_url=(_entry_image(parsed_entry, raw_content) or "")[:1000] or None,
            published=min(_entry_published(parsed_entry), utcnow()),
            word_count=len(text.split()),
        )
        db.session.add(entry)
        existing_guids.add(guid)
        new_count += 1

    db.session.flush()
    _prune_entries(feed.id, max_entries)
    db.session.commit()
    return new_count


def add_feed(url: str) -> tuple[Feed | None, str | None]:
    """Find-or-create a Feed for a URL. Returns (feed, error)."""
    feed_url, error = discover_feed_url(url.strip())
    if not feed_url:
        return None, error
    feed = Feed.query.filter_by(url=feed_url).first()
    if feed:
        return feed, None
    feed = Feed(url=feed_url)
    db.session.add(feed)
    db.session.flush()
    refresh_feed(feed)
    if feed.last_error and not feed.entries.count():
        purge_feed(feed)
        db.session.commit()
        return None, f"Feed found but could not be read ({feed.last_error})."
    return feed, None


def refresh_all_feeds(app) -> None:
    from .models import int_setting
    with app.app_context():
        cap = int_setting("max_entries_per_feed", app.config["MAX_ENTRIES_PER_FEED"])
        feeds = Feed.query.all()
        for feed in feeds:
            try:
                refresh_feed(feed, cap)
            except Exception:
                log.exception("refresh failed for %s", feed.url)
                db.session.rollback()
