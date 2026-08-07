# Changelog

All notable changes to Hyprfeed are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and Hyprfeed uses
[Semantic Versioning](https://semver.org/).

## [1.0.0] — 2026-08-07

First stable release. ⚡

### Added

**Reading experience**
- Magazine view: a lead story with hero image and dek, followed by a mixed story grid
- Cards view: image-forward uniform grid
- List view: dense, scannable rows with unread markers
- Built-in reader with sanitized article content, reading-time estimate,
  previous/next navigation, and `j` / `k` / arrow-key shortcuts
- Light and dark themes (system-following or fixed) with an instant topbar toggle
- Inter Variable typeface embedded — no external font requests
- Responsive layout down to phones, with an off-canvas sidebar

**Feeds**
- Feed auto-discovery: paste any website URL and Hyprfeed finds its RSS/Atom
  feed via `<link rel="alternate">` tags and common feed paths
- Page watcher: follow sites that publish **no feed at all** — Hyprfeed watches
  the page, detects new article links heuristically, and enriches each story
  from the article's own Open Graph metadata (title, image, description,
  publish date)
- Background refresh on a configurable interval, with conditional requests
  (ETag / Last-Modified) to stay polite to servers
- Per-feed retention cap (`MAX_ENTRIES_PER_FEED`, default 300) with automatic
  pruning, including cleanup of read/saved markers for pruned stories
- Per-feed unread counts, feed renaming, favicons, and per-feed views

**Accounts & multi-user**
- Multi-user accounts with per-user subscriptions, read state, saved stories,
  and preferences (theme, default view, mark-read-on-open)
- Email-based usernames with case-insensitive matching
- Cloudflare Turnstile support on sign-in and registration (enabled by setting
  two environment variables; skipped entirely when unset)
- Admin role: the first registered account becomes admin — manage users, reset
  passwords, promote/demote admins, delete accounts, and open/close
  registration at runtime from the settings modal
- CSRF protection on every mutating request; allowlist HTML sanitizer for
  feed content

**Operations**
- Single-container Docker deployment with SQLite in a named volume
- Automatic in-place schema migrations on startup
- Gunicorn with access logging; cache-busted static assets

[1.0.0]: https://github.com/hyprlab/hyprfeed/releases/tag/v1.0.0
