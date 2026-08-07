<p align="center">
  <img src="hyprfeed/static/img/logo.svg" width="72" alt="Hyprfeed logo — a yellow lightning bolt">
</p>

<h1 align="center">Hyprfeed</h1>

<p align="center"><strong>Your sites, one beautiful magazine.</strong></p>

<p align="center">
  <a href="https://hub.docker.com/r/hyprlab/hyprfeed"><img src="https://img.shields.io/docker/v/hyprlab/hyprfeed?label=docker&color=F7DF1E" alt="Docker Hub"></a>
  <a href="https://github.com/hyprlab/hyprfeed/blob/main/CHANGELOG.md"><img src="https://img.shields.io/badge/version-1.0.0-F7DF1E" alt="Version 1.0.0"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-blue" alt="AGPL-3.0 license"></a>
</p>

Hyprfeed is a self-hosted, multi-user RSS reader that turns the sites you
follow into an elegant magazine. Paste any website URL — Hyprfeed discovers its
feed, and if the site doesn't publish one, it can watch the page itself and
turn new articles into stories.

## Features

- **Three view modes** — magazine (lead story + mixed grid), cards, and a
  compact list; switch from the topbar, per-user preference remembered
- **Feed auto-discovery** — paste `example.com` and Hyprfeed finds the RSS or
  Atom feed for you
- **Page watcher** — follow sites with *no feed at all*: Hyprfeed detects new
  article links on the page and enriches each story with the article's own
  title, image, description, and publish date
- **Built-in reader** — clean, sanitized article view with reading-time
  estimate and `j` / `k` keyboard navigation
- **Multi-user** — private subscriptions, read state, and saved stories per
  account; email-based sign-in
- **Admin panel** — the first registered account becomes admin: manage users,
  reset passwords, promote admins, and open/close registration at runtime
- **Cloudflare Turnstile** — optional bot protection on sign-in and sign-up
- **Light & dark themes** — follows your system or your choice, instant toggle
- **Self-contained** — Inter typeface embedded, no CDNs, no external services
  required, SQLite storage in a single Docker volume

## Install with Docker Compose

1. Create a directory with this `docker-compose.yml` (or download it:
   `curl -O https://raw.githubusercontent.com/hyprlab/hyprfeed/main/docker-compose.yml`):

   ```yaml
   services:
     hyprfeed:
       image: hyprlab/hyprfeed:latest
       container_name: hyprfeed
       ports:
         # host:container — change the left side if 8098 is taken on your host
         - "8098:8000"
       environment:
         # Session signing key. If unset, one is generated and kept in the data volume.
         - SECRET_KEY=${SECRET_KEY:-}
         # Cloudflare Turnstile (optional — leave empty to disable the challenge)
         - TURNSTILE_SITE_KEY=${TURNSTILE_SITE_KEY:-}
         - TURNSTILE_SECRET_KEY=${TURNSTILE_SECRET_KEY:-}
         # Set to 0 to close sign-ups (the admin panel can also toggle this at runtime)
         - ALLOW_REGISTRATION=${ALLOW_REGISTRATION:-1}
         # How often feeds refresh in the background, in minutes
         - REFRESH_MINUTES=${REFRESH_MINUTES:-15}
         # How many stories each feed keeps; older ones are pruned
         - MAX_ENTRIES_PER_FEED=${MAX_ENTRIES_PER_FEED:-300}
       volumes:
         - hyprfeed-data:/data
       restart: unless-stopped

   volumes:
     hyprfeed-data:
   ```

2. (Optional) add a `.env` file next to it to set any of the variables above
   ([`.env.example`](.env.example)) — everything works with the defaults for a
   first run.

3. Start it:

   ```bash
   docker compose up -d
   ```

4. Open **http://localhost:8098** and create your account — **the first
   account registered becomes the admin**, so register yourself before opening
   the instance to others (or set `ALLOW_REGISTRATION=0` after you're in, or
   flip the toggle in Settings → Admin).

> **Note:** the downloaded compose file pulls the published image
> `hyprlab/hyprfeed`. If you `git clone` the repository instead, the included
> `docker-compose.override.yml` makes `docker compose up -d --build` build the
> image from your local source automatically.

### Updating

```bash
docker compose pull && docker compose up -d
```

Schema migrations run automatically on startup. Your data lives in the
`hyprfeed-data` volume and survives updates.

### Backup

Everything (database, generated secret key) is in the `/data` volume:

```bash
docker run --rm -v hyprfeed_hyprfeed-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/hyprfeed-backup.tgz -C /data .
```

## Configuration

Set these in `.env` (or the compose `environment:` block):

| Variable | Default | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | auto-generated in `/data` | Session signing key — set one explicitly if you run replicas |
| `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET_KEY` | empty (disabled) | Cloudflare Turnstile bot protection |
| `ALLOW_REGISTRATION` | `1` | Default for sign-ups; the admin panel toggle overrides it at runtime |
| `REFRESH_MINUTES` | `15` | Background feed refresh interval (`0` disables) |
| `MAX_ENTRIES_PER_FEED` | `300` | Stories kept per feed; older ones (read or not) are pruned |
| `DATA_DIR` | `/data` | Where SQLite and the secret key live |

### Cloudflare Turnstile

1. Create a widget in the [Cloudflare dashboard](https://dash.cloudflare.com/?to=/:account/turnstile)
   for the domain you serve Hyprfeed on.
2. Add both keys to `.env`:
   ```
   TURNSTILE_SITE_KEY=0x...
   TURNSTILE_SECRET_KEY=0x...
   ```
3. `docker compose up -d`

With the keys unset the challenge is skipped entirely — convenient for LAN-only
or development use.

## How the page watcher works

When you add a site and no RSS/Atom feed can be discovered, Hyprfeed offers
**"Follow without a feed."** It then:

1. scans the page for article-looking links (same site, wordy slugs,
   headline-length link text; navigation, tag, and author pages are filtered out),
2. fetches each *new* article once (at most 8 per refresh cycle) and reads its
   Open Graph metadata for the title, lead image, description, and publish date,
3. serves those stories like any other feed — unread counts, saving, and the
   reader all work the same.

Watched feeds are labeled with a "watcher" chip in Settings → Feeds. The reader
shows the article's summary with a link out to the site, out of respect for
publishers.

## Running from source

```bash
git clone https://github.com/hyprlab/hyprfeed.git && cd hyprfeed
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run.py            # http://localhost:8000
```

Or build the container yourself: `docker compose up -d --build`.

## Stack

Flask · SQLAlchemy · Flask-Login · feedparser · SQLite · gunicorn. No frontend
framework and no CDN dependencies — the [Inter](https://rsms.me/inter/)
variable font (SIL Open Font License) is bundled in the image.

## License

Hyprfeed is free software, released under the
[GNU Affero General Public License v3.0](LICENSE) (AGPL-3.0). You may run,
study, share, and modify it. If you run a modified version as a network
service, the AGPL requires you to offer its source code to your users — the
"Source" link in the app's settings makes that easy to satisfy.

© 2026 Hyprlab
