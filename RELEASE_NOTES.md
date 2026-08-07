# Release Notes

Plain-English notes on what each Hyprfeed release means for you. The full
technical log lives in [CHANGELOG.md](CHANGELOG.md).

## 1.3.0 — Unreleased — Your reader, your rules

Stories can now be **hidden** (with undo), everything you've read lives in a
new **History** view, and unread counts update the moment you open a story.
Feeds are managed from one **Reading & Feeds** tab — add them, drag them into
your preferred sidebar order, or sort alphabetically with a tap. Accounts got
display names shown in the sidebar, admins can create users with roles, and
feed lookups retry automatically so flaky first attempts are a thing of the
past.

## 1.2.0 — 2026-08-07 — The setup wizard

New installs are greeted by a guided setup: create your admin account, tune
your instance, and follow your first sites — all in about a minute. Refresh
cadence and how many stories each feed keeps are now controlled by admins in
**Settings → Admin** (no more editing `.env`), and interval changes apply
without a restart.

## 1.1.0 — 2026-08-07 — The About tab

Settings grew an **About** tab: version at a glance, the stack Hyprfeed is
built with, and these release notes plus the full changelog — right inside the
app, so you can see what changed after every update without leaving your
reader. The settings window also keeps a steady height now instead of resizing
as you move between tabs.

## 1.0.0 — 2026-08-07 — First release

Hyprfeed turns the sites you follow into one beautiful magazine.

- **Read your way** — magazine, cards, or list views, light or dark, with a
  clean built-in reader.
- **Follow anything** — paste a website address and Hyprfeed finds its feed.
  No feed? Hyprfeed can watch the page and turn new articles into stories.
- **Yours and your people's** — multi-user accounts with private
  subscriptions, read state, and saved stories; the first account becomes the
  admin with a built-in user manager.
- **Easy to run** — one Docker container, one data volume, optional Cloudflare
  Turnstile protection. Free software under the AGPL-3.0.
