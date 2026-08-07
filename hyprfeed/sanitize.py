"""Small allowlist HTML sanitizer for feed content (stdlib only)."""
import re
from html import escape
from html.parser import HTMLParser

ALLOWED = {
    "p": (), "br": (), "hr": (),
    "a": ("href",),
    "strong": (), "b": (), "em": (), "i": (), "u": (), "s": (), "mark": (), "small": (),
    "blockquote": (), "q": (),
    "ul": (), "ol": (), "li": (),
    "h1": (), "h2": (), "h3": (), "h4": (), "h5": (), "h6": (),
    "pre": (), "code": (),
    "img": ("src", "alt", "title"),
    "figure": (), "figcaption": (),
    "table": (), "thead": (), "tbody": (), "tr": (), "th": (), "td": (),
    "sup": (), "sub": (),
}
VOID = {"br", "hr", "img"}
# Headings in article bodies get demoted so they sit under the reader's own title.
DEMOTE = {"h1": "h3", "h2": "h3", "h5": "h4", "h6": "h4"}
DROP_WITH_CONTENT = {"script", "style", "iframe", "object", "embed", "form", "svg", "video", "audio", "noscript"}

_SAFE_URL = re.compile(r"^(https?:)?//|^https?:|^/|^#|^mailto:", re.I)


class _Sanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if self.skip_depth:
            if tag in DROP_WITH_CONTENT:
                self.skip_depth += 1
            return
        if tag in DROP_WITH_CONTENT:
            self.skip_depth = 1
            return
        if tag not in ALLOWED:
            return
        allowed_attrs = ALLOWED[tag]
        parts = []
        for name, value in attrs:
            if name in allowed_attrs and value:
                if name in ("href", "src") and not _SAFE_URL.match(value.strip()):
                    continue
                parts.append(f' {name}="{escape(value, quote=True)}"')
        if tag == "a":
            parts.append(' target="_blank" rel="noopener noreferrer"')
        if tag == "img":
            parts.append(' loading="lazy"')
        out_tag = DEMOTE.get(tag, tag)
        self.out.append(f"<{out_tag}{''.join(parts)}{' /' if tag in VOID else ''}>")

    def handle_endtag(self, tag):
        if self.skip_depth:
            if tag in DROP_WITH_CONTENT:
                self.skip_depth -= 1
            return
        if tag in ALLOWED and tag not in VOID:
            self.out.append(f"</{DEMOTE.get(tag, tag)}>")

    def handle_data(self, data):
        if not self.skip_depth and data:
            self.out.append(escape(data))


def sanitize_html(html: str) -> str:
    if not html:
        return ""
    s = _Sanitizer()
    try:
        s.feed(html)
        s.close()
    except Exception:
        return escape(strip_tags(html))
    return "".join(s.out)


class _Stripper(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in DROP_WITH_CONTENT:
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag in DROP_WITH_CONTENT and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        if not self.skip_depth:
            self.chunks.append(data)


def strip_tags(html: str) -> str:
    """Plain text from HTML, whitespace collapsed."""
    if not html:
        return ""
    s = _Stripper()
    try:
        s.feed(html)
        s.close()
    except Exception:
        pass
    return re.sub(r"\s+", " ", " ".join(s.chunks)).strip()


_IMG_SRC = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.I)


def first_image(html: str) -> str | None:
    if not html:
        return None
    m = _IMG_SRC.search(html)
    if m and _SAFE_URL.match(m.group(1).strip()):
        return m.group(1).strip()
    return None
