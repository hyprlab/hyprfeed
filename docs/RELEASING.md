# Releasing

How versions are numbered, when releases happen, and the exact steps.
Hyprfeed has one channel: stable releases from `main`, plus urgent patches.

## Versions: strict SemVer

Every release follows [Semantic Versioning 2.0.0](https://semver.org/). For an
app, the "public API" is whatever an existing install and its users depend on:
the data volume, the configuration, the URLs, and the features.

| Bump | When | Examples |
| --- | --- | --- |
| **MAJOR** `2.0.0` | Anything an existing install can't take without help | A migration an older version can't read back; a removed feature or setting; a renamed or removed environment variable; a changed URL other things link to; a changed volume path or port |
| **MINOR** `1.10.0` | New, backward-compatible functionality, or a deprecation | A new feature, setting, view or shelf; a new optional environment variable |
| **PATCH** `1.9.6` | Backward-compatible fixes only | A bug fix, a performance fix, a security fix with no behavior change |

`tools/next-version.sh` reads the Conventional Commit types since the last
release and says which bump they call for: `!` or a `BREAKING CHANGE:` footer
is major, `feat` is minor, `fix`, `perf` and `revert` are patch.
`tools/prepare-release.sh` refuses a version that disagrees unless told
`FORCE_VERSION=1`. The tool cannot see everything, so read the commits too:
a `fix` that changes the schema irreversibly is still MAJOR.

**Before any release, say plainly if the requested version does not fit** what
the commits since the last tag contain, and what SemVer calls for instead. The
maintainer decides; a mismatch has to be a decision, not an accident. A batch
with no features is a patch, not a minor.

A version never counts backwards, and a released version is never reused. The
version lives in one place, `__version__` in `hyprfeed/__init__.py`, and the
newest `CHANGELOG.md` section must match it (`tools/check-docs.py`).

Commits before 1.10.0 predate these rules and are not Conventional Commits;
the tools only read commits since the last tag, so that doesn't matter.

## Channels and cadence

| | Branch | Version | Docker tags | GitHub release |
| --- | --- | --- | --- | --- |
| Development | `main` | the last release, plus `## Unreleased` in the changelog | none | none |
| Stable | `main` | `X.Y.Z` | `:X.Y.Z`, `:X.Y`, `:latest` | release |
| Urgent patch | `stable-X.Y` | `X.Y.Z+1` | as stable | release |

1. **Work lands on `main`.** Commits stay local until the maintainer says to
   push or ship. Every user-visible change adds a line under `## Unreleased`.
2. **Releases happen only on request** ("ship it"), and batch whatever `main`
   has gathered.
3. **Patches between releases are for urgent fixes only:** a crash, data loss,
   a security hole, an instance that can't start or can't sign anyone in, when
   `main` holds unreleased work that isn't ready. See
   [Urgent patches](#urgent-patches). Otherwise a fix waits for the next
   release, which is a patch release if it carries no features.

## Before any release

- `python3 tools/check-docs.py` passes. A release does not go out while it fails.
- The changelog entries are written in the project's prose style
  ([CONTRIBUTING.md](CONTRIBUTING.md#prose-style)): what changed, from the
  user's side, factual, no marketing and no emoji.
- Every contributor in the release is in `data/CONTRIBUTORS` **before** the
  notes are generated, or `tools/release-notes.sh` strips their @.
- `git log origin/main..main --format=%B | grep -iE 'anthropic|claude'` prints
  nothing. The `pre-push` hook checks the same thing.

## Prepare

On `main`, with the changelog's `## Unreleased` section written:

```sh
tools/prepare-release.sh               # version from next-version.sh
```

That runs the docs check, turns `## Unreleased` into a dated `## [X.Y.Z]` section, sets
`__version__`, commits `chore(release): X.Y.Z`, tags it, and stops. Nothing is
pushed.

## Publish

```sh
git push origin main vX.Y.Z
tools/release-notes.sh X.Y.Z > /tmp/notes-X.Y.Z.md
gh release create vX.Y.Z --title "vX.Y.Z" --notes-file /tmp/notes-X.Y.Z.md
tools/publish-image.sh X.Y.Z
docker compose pull && docker compose up -d     # the maintainer's own instance
```

The release title is the version and nothing else: no name, no tagline. The
body is that version's changelog section plus the generated list of commits;
never hand `CHANGELOG.md` itself to `gh release create`. There is no separate
release-notes file: the changelog is the single record.

Then reply to and close every issue the release fixes, and delete the
superseded release, if any (below).

## Urgent patches

Only for a crash, data loss, a security hole, or an instance that can't start
or can't sign anyone in, while `main` holds work that can't ship yet.

1. Fix it on `main` first, in its own commit, so it cherry-picks cleanly.
2. Cut the branch lazily, from the last release tag, never from main:
   `git branch stable-X.Y vX.Y.Z` (skip if it exists).
3. `git checkout stable-X.Y && git cherry-pick <sha>`, add the changelog line
   under `## Unreleased`, then `tools/prepare-release.sh X.Y.Z+1`.
4. Publish as above, pushing `stable-X.Y` instead of `main`.
5. Merge `stable-X.Y` back into `main`, so the changelog entry survives.
6. Never delete a `stable-X.Y` branch: patch commits may exist only there.

## The Releases page

Keep it short: the newest release of each `X.Y` line. When a patch supersedes
`X.Y.Z`, delete the superseded release and its tag, but only after the new one
is published, `releases/latest` points at it, and its notes were generated
(the notes diff against the previous tag). Before deleting a tag, check its
commit is reachable from a branch that stays. Docker image tags are never
deleted: someone may have pinned one.

## Docker images

`tools/publish-image.sh` builds from the tag with `git archive`, not from the
working tree, so the image is exactly what was released. It pushes
`linux/amd64` only; set `PLATFORMS=linux/amd64,linux/arm64` once the host's
buildx has an arm64 builder.
