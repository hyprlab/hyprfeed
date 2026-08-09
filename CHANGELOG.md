# Changelog

All notable changes to Hyprfeed are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and Hyprfeed uses
[Semantic Versioning](https://semver.org/).

## [1.8.0] — 2026-08-09

### Added
- Filter menu in the topbar beside the view switcher: narrow any feed to its
  Unread, Saved, Skipped, or History stories, and switch shelves the same way
  at the top level. The active narrowing shows as a chip beside the feed name,
  and view switching keeps both the feed and the filter

## [1.7.5] — 2026-08-09

### Changed
- Undo toasts dismiss after 3.5s instead of 5s

## [1.7.4] — 2026-08-08

### Added
- Mark-all-as-skipped toolbar button beside mark-all-as-read: skips every
  story in the current feed (or all feeds) behind a scope-aware confirm;
  everything lands in the Skipped bin, individually restorable

## [1.7.3] — 2026-08-08

### Changed
- "Hidden" is now "Skipped": the card action is Skip (double-chevron icon),
  skipped stories collect in a Skipped sidebar bin, and Restore brings one
  back; old filter=hidden links still work
- Sidebar shelf order is now Unread, All stories, Saved, Skipped, History
- Saved is immune to skip: a story that is both saved and skipped stays
  visible in Saved while hidden everywhere else
- The undo toast slides down and fades out instead of vanishing

## [1.7.2] — 2026-08-08

### Added
- Swipe gestures on touch devices: swipe a story left to hide it or right to
  save it and mark it read. Cards track the finger 1:1, an action pill slides
  in from the edge you're swiping toward (arming in volt at the 60%
  threshold), and completed swipes slide out while the cards below glide up
  into the space. Everything is undoable from the toast
- Hidden shelf in the sidebar: hidden stories collect there newest-first
  until retention prunes them; the eye button (or a left swipe, relabeled
  Unhide) restores a story

### Fixed
- Refreshing no longer flashes a stale page containing since-hidden stories:
  dynamic pages now send Cache-Control: no-store

## [1.7.1] — 2026-08-08

### Added
- Copy-link button in the reader toolbar with a "Copied" tooltip; falls back
  to a legacy copy path on plain-http LAN deployments

### Changed
- Stories read in the reader now leave the Unread view when the reader
  closes (All stories keeps them greyed out); an emptied Unread page reloads
  into the "All caught up" state

## [1.7.0] — 2026-08-08

### Added
- Feed groups: create named groups in Settings → Reading & Feeds and organize
  everything by drag and drop. Drop a feed onto a group to file it (nested
  feeds show indented under a tree rail); groups are sealed containers, so
  moving one carries its feeds and can never capture neighbors. Groups render
  as expandable/collapsible sidebar sections with rolled-up unread counts and
  per-user remembered collapse state, and can be ordered anywhere between
  ungrouped feeds — the sidebar and the settings list share one interleaved
  order. Deleting a group keeps its feeds; A→Z/Z→A sorts within each section

### Changed
- Desktop settings modal grows to 80vh

## [1.6.2] — 2026-08-08

### Changed
- Settings modal fills the whole screen on phones; the tab bar stays on one
  swipeable row (with edge fades on overflow) and Admin fields stack vertically
- The article reader goes full-bleed on phones, edge to edge and
  safe-area aware
- The About tab shows only the changelog (open by default, with a "latest"
  chip); the separate release notes were retired

### Removed
- `RELEASE_NOTES.md` — the changelog is the single record of changes

### Fixed
- Shorts backdrops actually blur now: many channels serve Shorts thumbnails
  as 4:3 files with pillarbox bars baked in, so the blur layer was sampling
  black. The image is cropped to its central 9:16 slice and the blur layer
  zooms past the bars to sample real content

## [1.6.1] — 2026-08-07

### Added
- Pull-to-refresh on touch devices: drag down from the top of the feed to
  trigger a real feed refresh, with a volt indicator that arms at the
  threshold and spins while fetching

### Changed
- Feed titles link out: the topbar title in a feed view and the reader's
  feed kicker open the publisher's homepage in a new tab
- Card actions (save/hide) moved up to the kicker row so they never collide
  with text on touch screens; magazine cards gained an author/read-time line
- YouTube thumbnails render uncropped over a blurred copy of themselves
  instead of black letterbox bars (Shorts included)

## [1.6.0] — 2026-08-07

### Added
- YouTube channels as feeds: paste any channel, @handle, or video URL and
  Hyprfeed resolves it to the channel's feed; videos arrive with thumbnails,
  play embedded in the reader (privacy-enhanced youtube-nocookie player), and
  channels sit in their own "YouTube" group in the sidebar
- Live search: press Ctrl/⌘ K (or the topbar magnifier) for a command-palette
  overlay that searches your stories and feeds as you type — arrow keys to
  navigate, Enter opens the story in the reader
- Four more setup-wizard suggestions: The Atlantic, Tom's Hardware,
  Mother Jones, and BBC News

## [1.5.2] — 2026-08-07

### Changed
- Page-watcher stories now carry the article's real publish date far more
  often: extraction falls back through JSON-LD `datePublished`, more meta-tag
  names, `<time datetime>`, and dates embedded in the URL before resorting to
  first-seen time
- Reader toolbar back to the original layout: close button on the left,
  story controls on the right

## [1.5.1] — 2026-08-07

### Added
- Apple touch icon: the dimensional bolt art is served at 180px and linked
  from every page, so adding Hyprfeed to an iOS home screen shows the icon
- Brand asset set in `assets/icons/`: flat bolt PNGs (light + dark volt,
  16–1024px), charcoal launcher tiles, and Android adaptive icon layers
  (extracted glossy-bolt foreground + gradient background) built from the
  1024px source art

## [1.5.0] — 2026-08-07

### Added
- Google News fallback: when a site hard-blocks automated readers (e.g.
  Reuters), the add dialog and setup wizard explain what happened and offer —
  as an explicit choice — Google News' public site-scoped feed, subscribed
  under a "Site (via Google News)" name
- The page-watcher offer now appears on any feed-add failure where the page
  has recognizable articles, not just when no feed is advertised (fixes
  apnews.com, whose advertised feed is retired and answers 401)

### Changed
- Bot-wall responses (401/403) get a browser-UA retry and an honest
  "blocks automated readers" error message instead of a bare status code

## [1.4.0] — 2026-08-07

### Added
- OPML import and export in Settings → Reading & Feeds: export preserves your
  sidebar order and marks page-watcher feeds so they survive a round-trip;
  import subscribes instantly (up to 500 feeds, duplicates skipped) and
  fetches new feeds in the background
- Magazine view: a full-width feature card breaks up the grid after every
  ~4 rows of cards

### Changed
- Clicking your name in the sidebar opens Settings on the Account tab
- Reader toolbar: controls moved to the left, close button to the right

### Fixed
- Feeds with multiple content blocks per entry (e.g. Tom's Hardware) stored
  the author bio instead of the article — the longest block is now selected

## [1.3.0] — 2026-08-07

### Added
- Display names: set during setup, registration, or in Settings → Account;
  the sidebar shows name and email together, and admins can set names when
  creating accounts
- Admin user creation from Settings → Admin: email, temporary password, and
  role (admin or standard user), joining the existing reset/promote/delete
- Feed management upgrades in the merged **Reading & Feeds** tab: add feeds
  (with the page-watcher fallback), drag-and-drop reordering that drives the
  sidebar order, and one-tap A→Z / Z→A sorting
- Hide stories: an eye-off button on every story hides it from all views,
  with an Undo action in the toast
- History view in the sidebar: everything you've read, most recent first
- Manual read toggle in the reader when mark-read-on-open is off
- Setup wizard offers "Follow without a feed" for sites without RSS

### Changed
- Reading and Feeds tabs merged into one "Reading & Feeds" tab
- Opening a story now updates the sidebar unread counts live, and stories
  are only greyed out once actually read
- Feed fetching uses a pooled session with automatic retries and a
  browser-UA fallback, fixing "no feed found" errors that succeeded on a
  manual second try
- Built With text is full black in light mode for contrast over the hero

### Fixed
- Horizontal overflow scrollbars in the About tab

## [1.2.0] — 2026-08-07

### Added
- First-run setup wizard: on a fresh install every request steers to `/setup`,
  which walks through creating the admin account, tuning instance settings
  (registration, refresh cadence, per-feed story retention), and following
  first sites (with one-tap suggestions) — then drops into the app signed in
- Instance settings are now administerable at runtime from Settings → Admin:
  background refresh interval and stories-kept-per-feed live in the database,
  editable by admins, with the `REFRESH_MINUTES` / `MAX_ENTRIES_PER_FEED` env
  vars serving as defaults for fresh installs; the background refresher picks
  up interval changes without a restart
- Hyprlab icon next to "Built by" on the About tab

### Changed
- New tagline — "A self-hosted RSS reader for the open web" — on the sign-in
  screen, the account-creation screen, and the About tab

## [1.1.0] — 2026-08-07

### Added
- About tab in the settings modal: animated hero with app version, license,
  and source links; "Built with" tech stack; release notes and changelog
  rendered in-app from `RELEASE_NOTES.md` / `CHANGELOG.md` (parsed and cached
  by `hyprfeed/about_docs.py` — editing the Markdown is the only step needed)
- `RELEASE_NOTES.md` — plain-English release notes alongside the changelog
- Full docker-compose example embedded in the README

### Changed
- Settings modal now has a fixed height; switching tabs no longer resizes it,
  and each pane scrolls internally
- Version/license line moved from the Account pane to the About tab

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

**Licensing**
- Released as free software under the GNU AGPL-3.0

**Operations**
- Single-container Docker deployment with SQLite in a named volume
- Automatic in-place schema migrations on startup
- Gunicorn with access logging; cache-busted static assets

[1.8.0]: https://github.com/hyprlab/hyprfeed/releases/tag/v1.8.0
[1.7.5]: https://github.com/hyprlab/hyprfeed/releases/tag/v1.7.5
[1.7.4]: https://github.com/hyprlab/hyprfeed/releases/tag/v1.7.4
[1.7.3]: https://github.com/hyprlab/hyprfeed/releases/tag/v1.7.3
[1.7.2]: https://github.com/hyprlab/hyprfeed/releases/tag/v1.7.2
[1.7.1]: https://github.com/hyprlab/hyprfeed/releases/tag/v1.7.1
[1.7.0]: https://github.com/hyprlab/hyprfeed/releases/tag/v1.7.0
[1.6.2]: https://github.com/hyprlab/hyprfeed/releases/tag/v1.6.2
[1.6.1]: https://github.com/hyprlab/hyprfeed/releases/tag/v1.6.1
[1.6.0]: https://github.com/hyprlab/hyprfeed/releases/tag/v1.6.0
[1.5.2]: https://github.com/hyprlab/hyprfeed/releases/tag/v1.5.2
[1.5.1]: https://github.com/hyprlab/hyprfeed/releases/tag/v1.5.1
[1.5.0]: https://github.com/hyprlab/hyprfeed/releases/tag/v1.5.0
[1.4.0]: https://github.com/hyprlab/hyprfeed/releases/tag/v1.4.0
[1.3.0]: https://github.com/hyprlab/hyprfeed/releases/tag/v1.3.0
[1.2.0]: https://github.com/hyprlab/hyprfeed/releases/tag/v1.2.0
[1.1.0]: https://github.com/hyprlab/hyprfeed/releases/tag/v1.1.0
[1.0.0]: https://github.com/hyprlab/hyprfeed/releases/tag/v1.0.0
