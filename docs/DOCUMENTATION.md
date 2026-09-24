# Documentation

Configuring and running Hyprfeed. Installing is in the
[README](../README.md#install-with-docker-compose).

## Configuration

Most day-to-day settings (registration, refresh cadence, story retention) are
managed in the app under Settings → Admin; the setup wizard seeds them on
first run. Environment variables provide secrets and fresh-install defaults.
Put them in a `.env` file next to `docker-compose.yml`
([`.env.example`](../.env.example) lists them all), then `docker compose up -d`
to apply.

| Variable | Default | What it does |
| --- | --- | --- |
| `SECRET_KEY` | generated in `/data` | Signs sessions. Set one explicitly if you run replicas |
| `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY` | empty (off) | Cloudflare Turnstile on sign-in and sign-up; see [Turnstile](#cloudflare-turnstile) |
| `ALLOW_REGISTRATION` | `1` | Fresh-install default; the Settings → Admin toggle overrides it |
| `REFRESH_MINUTES` | `15` | Fresh-install default; Settings → Admin overrides it (`0` pauses) |
| `MAX_ENTRIES_PER_FEED` | `300` | Fresh-install default; Settings → Admin overrides it |
| `DATA_DIR` | `/data` | Where SQLite and the secret key live |

## Cloudflare Turnstile

1. Create a widget in the [Cloudflare dashboard](https://dash.cloudflare.com/?to=/:account/turnstile)
   for the domain you serve Hyprfeed on.
2. Add both keys to `.env`:
   ```
   TURNSTILE_SITE_KEY=0x...
   TURNSTILE_SECRET_KEY=0x...
   ```
3. `docker compose up -d`

With the keys unset the challenge is skipped entirely, which suits LAN-only
or development use.

## How the page watcher works

When you add a site and no RSS or Atom feed can be discovered, Hyprfeed offers
**"Follow without a feed."** It then:

1. scans the page for article-looking links (same site, wordy slugs,
   headline-length link text; navigation, tag, and author pages are filtered out),
2. fetches each *new* article once (at most 8 per refresh cycle) and reads its
   Open Graph metadata for the title, lead image, description, and publish date,
3. serves those stories like any other feed: unread counts, saving, and the
   reader all work the same.

Watched feeds are labeled with a "watcher" chip in Settings → Reading & Feeds.
The reader shows the article's summary with a link out to the site, out of
respect for publishers.

## Updating

```sh
docker compose pull && docker compose up -d
```

Schema migrations run automatically on startup. A MAJOR version (`2.0.0`)
means an existing install needs something done by hand; the changelog says
what.

## Backups

Everything (the database and the generated secret key) is in the `/data`
volume:

```sh
docker run --rm -v hyprfeed_hyprfeed-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/hyprfeed-backup.tgz -C /data .
```

Stop the container first (`docker compose stop`) for a copy SQLite can't have
been writing to mid-way.

## Running from source

```sh
git clone https://github.com/hyprlab/hyprfeed.git && cd hyprfeed
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python run.py            # http://localhost:8000
```

Or build the container yourself: `docker compose up -d --build` picks up the
included `docker-compose.override.yml`, which builds from your checkout.
Contributing conventions are in [CONTRIBUTING.md](CONTRIBUTING.md).
