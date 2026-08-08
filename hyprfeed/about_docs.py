"""Parsed Changelog for the in-app About tab.

The canonical ``CHANGELOG.md`` at the repo root is the single source of
truth; this module parses it into version entries and renders their bodies
to HTML. Editing the Markdown is the only step needed to update the About
tab. Parsing is cached by file mtime, so dev edits appear without a restart.
"""
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import markdown as md_lib

_ROOT = Path(__file__).resolve().parent.parent
_CHANGELOG = _ROOT / "CHANGELOG.md"

_MD_EXT = ["extra", "sane_lists"]

# "## [1.1.0] — 2026-08-07 — Short title" (brackets, "(latest)", date and
# title all optional; — – or - accepted as separators)
_HEADER = re.compile(r"^##\s+\[?(\d[\w.\-]*)\]?\s*(\(latest\))?\s*(.*)$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_LINK_REF = re.compile(r"^\[[^\]]+\]:\s+\S+\s*$", re.M)


@dataclass
class Entry:
    version: str
    date_label: str   # "Aug 7, 2026" — "" when the header has no date
    title: str        # optional short headline after the date
    is_latest: bool
    body_html: str


def _parse_header_rest(rest: str) -> tuple[str, str]:
    """Split '2026-08-07 — Short title' into (date_label, title)."""
    parts = [p.strip() for p in re.split(r"\s+[—–-]\s+|^[—–-]\s+", rest) if p.strip()]
    date_label, title_parts = "", []
    for part in parts:
        if not date_label and _ISO_DATE.match(part):
            try:
                date_label = datetime.strptime(part, "%Y-%m-%d").strftime("%b %-d, %Y")
                continue
            except ValueError:
                pass
        title_parts.append(part)
    return date_label, " — ".join(title_parts)


def _parse(path: Path) -> list[Entry]:
    if not path.exists():
        return []
    entries: list[Entry] = []
    current: dict | None = None
    body: list[str] = []

    def flush():
        if current is None:
            return
        raw = _LINK_REF.sub("", "\n".join(body)).strip()
        entries.append(Entry(
            version=current["version"],
            date_label=current["date_label"],
            title=current["title"],
            is_latest=current["latest"],
            body_html=md_lib.markdown(raw, extensions=_MD_EXT),
        ))

    for line in path.read_text(encoding="utf-8").splitlines():
        m = _HEADER.match(line)
        if m:
            flush()
            date_label, title = _parse_header_rest(m.group(3) or "")
            current = {
                "version": m.group(1),
                "latest": bool(m.group(2)),
                "date_label": date_label,
                "title": title,
            }
            body = []
        elif current is not None:
            body.append(line)
    flush()
    if entries and not any(e.is_latest for e in entries):
        entries[0].is_latest = True
    return entries


_cache: dict[str, tuple[int, list[Entry]]] = {}


def _cached(path: Path) -> list[Entry]:
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        return []
    hit = _cache.get(str(path))
    if hit and hit[0] == mtime:
        return hit[1]
    parsed = _parse(path)
    _cache[str(path)] = (mtime, parsed)
    return parsed


def changelog() -> list[Entry]:
    return _cached(_CHANGELOG)
