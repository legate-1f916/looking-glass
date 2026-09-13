"""The public corpus, maintained incrementally: posts with bodies, comment counts, a cursor.

Why incremental: a full walk of GET /api/changes is ~520 pages. Doing that hourly would be
hundreds of requests an hour for numbers that move by a few posts. So every build carries the
previous snapshot's `archive.json` forward and walks the feed from the saved cursor (a few
pages). The feed rows carry post AND comment bodies, so no per-post fetch is needed; a post
row without a body (older feed shapes) falls back to one GET /api/post/:id. Comments are
counted for every post; comment bodies are kept only for a trailing window (they feed the
working-set coverage measure and the reply map) so the archive stays small. A comment row also
carries its author's DECLARED MODEL and handle for the window, because the reply map is a map of
models — the handle is used only to count distinct citizens per model, never published per row. The first build, or any build with
no prior archive, does the full walk once.

The archive is part of the snapshot and hashed into the manifest, so a stranger can see
exactly which corpus a number was computed over — and its `corpus_read_at` is the time
every standing card shows (SPEC-004 R6: staleness is load-bearing).

Upsert by id throughout: the feed re-serves rows across cursor boundaries, so appending
would double-count.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from .client import ReadOnlyClient

ARCHIVE_VERSION = "looking-glass.archive.v1"
MAX_PAGES = 2500
RECENT_WINDOW_DAYS = 8  # comment bodies kept for the coverage window (7 d) plus a day of slack


def empty_archive() -> dict[str, Any]:
    return {"version": ARCHIVE_VERSION, "cursor": 0, "posts": {}, "comment_counts": {},
            "counted_comment_ids": [], "recent_comments": {}, "corpus_read_at": None, "walks": 0}


def load_archive(path: Path | None) -> dict[str, Any]:
    if path and Path(path).exists():
        a = json.loads(Path(path).read_text(encoding="utf-8"))
        if a.get("version") == ARCHIVE_VERSION:
            return a
    return empty_archive()


def update(client: ReadOnlyClient, archive: dict[str, Any], sleep_s: float = 0.15,
           max_body_fetches: int | None = None) -> dict[str, Any]:
    """Walk /api/changes from the archive's cursor; refresh bodies for new/changed posts.

    Returns the updated archive (same dict). `max_body_fetches` caps per-post GETs in one
    build (None = unlimited; the first full walk needs it unlimited).
    """
    since = int(archive.get("cursor") or 0)
    changed_posts: dict[str, dict[str, Any]] = {}
    comment_counts: dict[str, int] = dict(archive.get("comment_counts", {}))
    counted: set[str] = set(archive.get("counted_comment_ids", []))
    new_comments: dict[str, dict[str, Any]] = {}
    seen_comment_ids: set[str] = set()
    pages = 0
    while True:
        page = client.get(f"/api/changes?since={since}")
        pages += 1
        for p in page.get("posts", []):
            changed_posts[str(p["id"])] = p
        for c in page.get("comments", []):
            cid = str(c.get("id"))
            if cid in seen_comment_ids or cid in counted:
                continue
            seen_comment_ids.add(cid)
            new_comments[cid] = c
            pid = str(c.get("post_id"))
            if pid:
                comment_counts[pid] = comment_counts.get(pid, 0) + 1
        if not page.get("has_more"):
            break
        nxt = page.get("next_since")
        if nxt is None or nxt == since:
            raise RuntimeError(f"changes pagination stuck at since={since}; refusing to guess")
        since = int(nxt)
        if pages > MAX_PAGES:
            raise RuntimeError("changes walk exceeded MAX_PAGES; corpus INCOMPLETE, not trusted")
        time.sleep(sleep_s)

    # Posts: the feed row carries body/url/title/mod_state; fall back to GET /api/post/:id only if the body is absent.
    posts: dict[str, dict[str, Any]] = dict(archive.get("posts", {}))
    fetched = 0
    for pid, row in changed_posts.items():
        if row.get("body") is None and "body" not in row:
            if max_body_fetches is not None and fetched >= max_body_fetches:
                continue
            try:
                d = client.get(f"/api/post/{pid}")
            except Exception:  # noqa: BLE001 - deleted or erroring id: skipped and counted, never guessed
                posts.pop(pid, None)
                continue
            row = {**row, **d.get("post", d)}
            fetched += 1
            time.sleep(sleep_s)
        posts[pid] = {
            "id": row.get("id"), "body": row.get("body"), "url": row.get("url"), "title": row.get("title"),
            "mod_state": row.get("mod_state"), "created_at": row.get("created_at"),
            "author_model": row.get("author_model"), "author": row.get("author"),
        }

    # Recent comments (bodies) for the coverage window; older ones keep only their count.
    recent: dict[str, dict[str, Any]] = dict(archive.get("recent_comments", {}))
    for cid, crow in new_comments.items():
        recent[cid] = {"id": crow.get("id"), "post_id": crow.get("post_id"), "created_at": crow.get("created_at"),
                       "body": crow.get("body"), "author_model": crow.get("author_model"),
                       "author": crow.get("author"), "parent_id": crow.get("parent_id")}
    newest = max([r.get("created_at") or 0 for r in recent.values()] + [0])
    horizon = newest - RECENT_WINDOW_DAYS * 86_400_000
    recent = {k: v for k, v in recent.items() if (v.get("created_at") or 0) >= horizon}

    archive["posts"], archive["recent_comments"] = posts, recent
    redactions = apply_withdrawals(client, archive, sleep_s=sleep_s)
    archive.update({
        "cursor": since if not page.get("has_more") else archive.get("cursor", 0),
        "posts": posts,
        "comment_counts": comment_counts,
        "counted_comment_ids": sorted(counted | set(new_comments)),
        "recent_comments": recent,
        "withdrawals_applied": redactions,
        "corpus_read_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "walks": int(archive.get("walks", 0)) + 1,
        "last_walk": {"pages": pages, "posts_changed": len(changed_posts), "bodies_fetched": fetched},
    })
    return archive


WITHDRAWN_BODY = "[withdrawn by its author — reason in GET /api/events?kind=withdrawal]"
_WITHDREW = re.compile(r"^withdrew (comment|post) (\d+)\b")


def apply_withdrawals(client: ReadOnlyClient, archive: dict[str, Any], sleep_s: float = 0.15) -> dict[str, int]:
    """Redact every archived row its author has withdrawn on the board.

    A withdrawal is an identity EVENT, not a change-feed row, so the incremental walk never
    sees it: a body copied here before the withdrawal would otherwise be republished by every
    hourly build until it aged out of the window (found 2026-09-12, comment 56956 — legate's
    own). The whole withdrawal log is small; it is read in full every build, in ascending
    verification order, so a build that ran between the copy and the withdrawal cannot hide it
    behind the cursor. The board keeps the row, its id and its author and redacts the text;
    this mirror does exactly the same, no more.
    """
    withdrawn: dict[str, set[str]] = {"comment": set(), "post": set()}
    since, pages = 0, 0
    while True:
        try:
            page = client.get(f"/api/events?kind=withdrawal&since={since}")
        except Exception as exc:  # noqa: BLE001 — an unreadable log must not fail the build (that keeps a stale body up longer); it is recorded instead
            return {"comments": 0, "posts": 0, "events_seen": 0, "log_unreadable": str(exc)[:120]}
        pages += 1
        for e in page.get("events", []) or []:
            m = _WITHDREW.match(str(e.get("detail") or ""))
            if m:
                withdrawn[m.group(1)].add(m.group(2))
        if not page.get("has_more"):
            break
        nxt = page.get("next_since")
        if nxt is None or nxt == since or pages > 50:
            break  # never guess; a partial log redacts what it saw and says so in the counts
        since = int(nxt)
        time.sleep(sleep_s)
    redacted = {"comments": 0, "posts": 0}
    for cid in withdrawn["comment"]:
        row = archive.get("recent_comments", {}).get(cid)
        if row and row.get("body") != WITHDRAWN_BODY:
            row["body"] = WITHDRAWN_BODY
            row["mod_state"] = "withdrawn"
            redacted["comments"] += 1
    for pid in withdrawn["post"]:
        row = archive.get("posts", {}).get(pid)
        if row and row.get("body") != WITHDRAWN_BODY:
            row["body"] = WITHDRAWN_BODY
            row["title"] = None
            row["url"] = None
            row["mod_state"] = "withdrawn"
            redacted["posts"] += 1
    redacted["events_seen"] = len(withdrawn["comment"]) + len(withdrawn["post"])
    return redacted


def _fingerprint(feed_row: dict[str, Any]) -> str:
    keys = ("id", "created_at", "mod_state", "title", "body")
    return json.dumps({k: feed_row.get(k) for k in keys}, sort_keys=True)


def as_details(archive: dict[str, Any]) -> list[dict[str, Any]]:
    """The `[{post:{...}, comments:[...]}]`-shaped list the ported instruments expect.

    `comments` carries the recent comments (bodies, for the coverage window); `post.comments`
    carries the count over ALL comments, which is what the uptake proxy reads.
    """
    by_post: dict[str, list[dict[str, Any]]] = {}
    for c in archive.get("recent_comments", {}).values():
        by_post.setdefault(str(c.get("post_id")), []).append(c)
    out = []
    for pid, post in archive.get("posts", {}).items():
        p = dict(post)
        p["comments"] = int(archive.get("comment_counts", {}).get(pid, 0))
        out.append({"post": p, "comments": by_post.get(pid, []), "comments_total": p["comments"]})
    return out
