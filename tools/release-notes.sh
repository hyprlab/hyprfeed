#!/usr/bin/env bash
# Print the GitHub release body for one version.
#
#   tools/release-notes.sh 1.3.0 > /tmp/notes.md
#
# The body is that version's CHANGELOG section, its Keep a Changelog headings
# renamed (Added becomes "New features:", Changed "Changes:", Fixed "Fixes:").
# It is a draft: shorten each line to a few words and its issue, as in
# docs/RELEASING.md ("Release notes"), before `gh release create`. Never hand
# CHANGELOG.md itself to `gh release create`: every release page would carry
# the whole history.
#
# With the tag pushed, it appends a "Full changelog" compare link against the
# previous tag OF THE SAME KIND (a beta against the previous beta, a stable
# against the previous stable). No commit list: the compare link has it.
#
# GitHub keeps every line break in a release body, so paragraphs and list items
# are unwrapped to one line each. An @handle keeps its @ only if the person is
# in data/CONTRIBUTORS: an @ notifies someone and reads as authorship, so it is
# for people whose work is in the release, not for whoever reported the bug.
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="${1:?usage: tools/release-notes.sh X.Y.Z[-beta.N]}"
TAG="v$VERSION"

{
python3 - "$VERSION" <<'PY'
import re, sys, pathlib
version = sys.argv[1]
text = pathlib.Path("CHANGELOG.md").read_text(encoding="utf-8")
m = re.search(r"^##\s+\[?" + re.escape(version) + r"\]?[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
if not m:
    sys.exit(f"CHANGELOG.md has no section for {version}.")
names = {"added": "New features", "changed": "Changes", "fixed": "Fixes",
         "translated": "Translations", "translations": "Translations"}
out, buf = [], []
def flush():
    if buf:
        out.append(" ".join(buf)); buf.clear()
for line in m.group(1).strip().splitlines():
    s = line.strip()
    if not s:
        flush(); out.append("")
    elif h := re.match(r"^###\s+(.+?):?$", s):
        flush()
        out += [f"### {names.get(h.group(1).lower(), h.group(1))}:", ""]
    elif re.match(r"^([-*]|\d+\.|#+)\s", s):
        flush(); buf.append(s)
    else:
        buf.append(s)
flush()
print(re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip())
PY

if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
    if [[ "$VERSION" == *-* ]]; then
        prev=$(git tag -l 'v*-*' --sort=-v:refname | grep -vx "$TAG" | head -1 || true)
    else
        prev=$(git tag -l 'v*' --sort=-v:refname | grep -vE -- '-' | grep -vx "$TAG" | head -1 || true)
    fi
    if [ -n "$prev" ]; then
        repo=$(git remote get-url origin 2>/dev/null | sed -E 's#^(git@[^:]+:|ssh://git@[^/]+/|https://github\.com/)##; s#\.git$##' || true)
        if [ -n "$repo" ]; then
            echo
            echo "---"
            echo
            echo "**Full changelog:** [$prev...$TAG](https://github.com/$repo/compare/$prev...$TAG)"
        fi
    fi
fi
} | python3 -c '
import re, sys, pathlib
p = pathlib.Path("data/CONTRIBUTORS")
known = set()
if p.exists():
    for line in p.read_text(encoding="utf-8").splitlines():
        m = re.search(r"@([A-Za-z0-9-]+)", line)
        if m and not line.lstrip().startswith("#"):
            known.add(m.group(1).lower())
text = sys.stdin.read()
text = re.sub(r"(?<![\w/])@([A-Za-z0-9-]+)",
              lambda m: m.group(0) if m.group(1).lower() in known else m.group(1), text)
sys.stdout.write(text)
'
