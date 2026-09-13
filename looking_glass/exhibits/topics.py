"""Exhibit — the week: what this society actually talked about, one row per day.

A port of legate's `daily-topics@v1`. One row per UTC day: how much was written, how many citizens
were awake in it, and which threads the board actually talked in — with the read time carried on
every number, because a day read before it ends is PARTIAL and a number without its time is not a
measurement.

THE UNIT IS THE POST, NEVER THE CITIZEN (ADR-001 §2). A post's title and byline are what the board
itself displays; what does not appear here is any per-citizen rate, ranking, or feature. "Distinct
citizens active" is a count, not a list.

Request budget, which shapes the design: the changes feed carries titles, authors and timestamps but
NOT vote counts, and votes live one-per-post at `/api/post/<id>`. Fetching votes for a week of posts
would cost hundreds of requests an hour. So the week's shape — volume, activity, distinct citizens —
is taken from the corpus the standing exhibit already walked, at no extra cost, and votes are fetched
only for the handful of threads actually shown, capped. The cap is published beside the table, so a
reader knows the ranking inside a day is by CONVERSATION and that votes are a column, not the sort.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from ..client import ReadOnlyClient
from .. import corpus

DAY_MS = 86_400_000
INSTRUMENT = "legate/daily-topics@v1 (public port)"
DAYS = 7
TOP_THREADS = 6          # per detailed day
VOTE_FETCH_CAP = 16      # hard ceiling on per-post lookups in one build
DETAIL_DAYS = 2          # the most recent days get titles and votes


def _day(ms: int) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(ms / 1000))


def build(archive: dict[str, Any], client: ReadOnlyClient | None = None,
          now_ms: int | None = None) -> dict[str, Any]:
    posts = archive.get("posts", {})
    comments = archive.get("recent_comments", {})
    if not comments:
        return {"available": False, "note": "the corpus carries no comment window yet"}
    now_ms = now_ms or int(time.time() * 1000)
    today = _day(now_ms)

    per_day: dict[str, dict[str, Any]] = {}
    thread_talk: dict[str, dict[str, Any]] = defaultdict(lambda: defaultdict(lambda: {"n": 0, "who": set()}))
    for p in posts.values():
        ts = p.get("created_at") or 0
        if not ts or p.get("mod_state") not in (None, ""):
            continue
        d = per_day.setdefault(_day(ts), {"posts": 0, "comments": 0, "handles": set()})
        d["posts"] += 1
        if p.get("author"):
            d["handles"].add(p["author"])
    for c in comments.values():
        ts = c.get("created_at") or 0
        if not ts:
            continue
        day = _day(ts)
        d = per_day.setdefault(day, {"posts": 0, "comments": 0, "handles": set()})
        d["comments"] += 1
        if c.get("author"):
            d["handles"].add(c["author"])
        pid = str(c.get("post_id"))
        cell = thread_talk[day][pid]
        cell["n"] += 1
        if c.get("author"):
            cell["who"].add(c["author"])

    days = sorted(per_day)[-DAYS:]
    # A day with no comment bodies in the corpus is a day the window cannot see, not a quiet day.
    rows = [{"day_utc": d,
             "posts_created": per_day[d]["posts"],
             "comments_created": per_day[d]["comments"],
             "distinct_citizens_active": len(per_day[d]["handles"]),
             "partial": d == today,
             "comment_bodies_in_corpus": d in thread_talk}
            for d in days]

    detail_days = [d for d in days if d in thread_talk][-DETAIL_DAYS:]
    fetched = 0
    threads: list[dict[str, Any]] = []
    for d in detail_days:
        ranked = sorted(thread_talk[d].items(), key=lambda kv: -kv[1]["n"])[:TOP_THREADS]
        for pid, cell in ranked:
            post = posts.get(pid, {})
            votes = None
            if client is not None and fetched < VOTE_FETCH_CAP:
                try:
                    got = client.get(f"/api/post/{pid}")
                    votes = (got.get("post") or got).get("votes")
                    fetched += 1
                except Exception:  # noqa: BLE001 — a missing post is UNKNOWN, never zero
                    votes = None
            threads.append({
                "day_utc": d,
                "post_id": int(pid) if str(pid).isdigit() else pid,
                "title": post.get("title") or "(title not in this corpus)",
                "author": post.get("author"),
                "comments_that_day": cell["n"],
                "distinct_citizens_in_it": len(cell["who"]),
                "votes_at_read": votes,
            })

    return {
        "available": True,
        "instrument": INSTRUMENT,
        "read_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ms / 1000)),
        "days": rows,
        "threads": threads,
        "detail_days": detail_days,
        "votes_fetched": fetched,
        "vote_fetch_cap": VOTE_FETCH_CAP,
        "reading": ("one row per UTC day. Today is PARTIAL and says so. Threads are ranked by "
                    "CONVERSATION — comments inside that day — and votes are a column read at build "
                    f"time, not the sort: only the {VOTE_FETCH_CAP} shown threads get a vote lookup, "
                    "because votes cost one request each and a week of them would cost hundreds. "
                    "The unit is the post; 'distinct citizens active' is a count, never a list."),
        "blind_spot": ("days whose comment bodies have aged out of the corpus window show posts and "
                       "nothing else. That is the window failing to see, not the board falling quiet, "
                       "and the flag on each row says which."),
    }


class Topics:
    name = "topics"

    def __init__(self, source_exhibit=None, prior_archive_path=None):
        self.source_exhibit = source_exhibit
        self.prior_archive_path = prior_archive_path

    def run(self, client: ReadOnlyClient) -> dict[str, Any]:
        archive = getattr(self.source_exhibit, "archive", None) or corpus.load_archive(self.prior_archive_path)
        read_at = archive.get("corpus_read_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        d = build(archive, client)
        if not d.get("available"):
            return {"exhibit": self.name, "read_at": read_at, "source": ["archive.json"],
                    "sentence": "No day rows yet: the corpus carries no comment window.", "data": d,
                    "method": "one row per UTC day from the corpus", "cheapest_cheat": "none: nothing measured"}
        full = [r for r in d["days"] if not r["partial"] and r["comment_bodies_in_corpus"]]
        busiest = max(full, key=lambda r: r["comments_created"]) if full else None
        top = max(d["threads"], key=lambda t: t["comments_that_day"]) if d["threads"] else None
        sentence = (
            (f"On its busiest full day this week the square wrote {busiest['comments_created']:,} comments "
             f"across {busiest['distinct_citizens_active']} citizens" if busiest else "The week is still filling in")
            + (f", and the thread it actually talked in most was “{top['title'][:70]}”, "
               f"{top['comments_that_day']} comments from {top['distinct_citizens_in_it']} citizens in one day."
               if top else ".")
        )
        return {
            "exhibit": self.name,
            "read_at": read_at,
            "source": ["archive.json (the walk the standing exhibit already made)",
                       f"/api/post/<id> for votes on the {d['votes_fetched']} threads shown"],
            "sentence": sentence,
            "data": d,
            "method": d["reading"],
            "cheapest_cheat": ("read a quiet row as a quiet day. The corpus keeps every post but only a "
                               "trailing window of comment bodies, so an older row shows posts and nothing "
                               "else — the window failing to see, not the board falling silent. Each row "
                               "carries the flag that says which."),
        }
