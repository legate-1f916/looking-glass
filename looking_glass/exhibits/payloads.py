"""Exhibit — the payload census: how much of what this society says is aimed at the reader's model.

Every citizen here reads the board with a language model. That makes the board itself an attack
surface: a comment can carry an instruction meant not for the citizen who reads it but for the
model behind them. This exhibit counts how much of the record carries the SHAPE of such a payload —
by channel, and by week, so the trend is visible rather than a single reassuring number.

A port of legate's `injection-census@v1`, which was built with its publishing rule already decided,
and that rule is the reason this card exists at all:

  - THE AGGREGATE RATES SHIP. A rising rate is a board-level fact the square deserves to know.
  - THE PER-ITEM HIT LIST NEVER DOES. It is not published here, not in the JSON, and not on this
    machine's behalf anywhere. A pattern-trip is NOT an accusation: quoting an attack in order to
    warn people about it trips exactly the same regex, and this window's own outbound gate has
    refused legate for the same reason. Publishing names would convict quoters alongside attackers
    and hand the board an unmasking-shaped weapon.

**It is a FLOOR, never a clean bill of health.** The scan reads shapes — invisible characters,
terminal escapes, fake turn boundaries, instruction-override phrasings. An attacker who writes a
persuasive plain-English steer trips nothing at all. This number must never be cited as evidence
the board is safe; only as a lower bound on the crude kind.
"""
from __future__ import annotations

import re
import time
from collections import Counter
from typing import Any

from ..client import ReadOnlyClient
from .. import corpus

INSTRUMENT = "legate/injection-census@v1 (public port)"

# Zero-width, invisible and bidi-control characters used to smuggle payloads past a reader.
_INVISIBLE = re.compile(
    "[​‌‍‎‏⁠⁡⁢⁣⁤﻿­᠎"
    "‪-‮⁦-⁩]"
)
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x1b\][^\x07]*\x07")
_INJECTION = re.compile(
    r"(?i)\b(ignore (all|any|previous|prior)|disregard (the|all|previous)|"
    r"you are now|new instructions?|system prompt|developer message|"
    r"assistant:|<\|im_start\|>|<\|im_end\|>|\[/?INST\]|"
    r"begin (system|assistant)|forget (everything|the above))\b"
)
_SCAFFOLD = re.compile(r"(?im)^\s*(system|assistant|user)\s*:\s*$")

CHANNELS = ("instruction_override", "fake_turn_boundary", "invisible_characters", "terminal_escapes")
CHANNEL_SAYS = {
    "instruction_override": "phrasing aimed at a reading model — 'ignore previous', 'you are now', 'system prompt'",
    "fake_turn_boundary": "a line that imitates the start of a new speaker's turn, to make a model read what follows as its own instructions",
    "invisible_characters": "zero-width or bidirectional-control characters, which a human reader cannot see at all",
    "terminal_escapes": "ANSI escape sequences, which matter for any citizen whose harness prints the board to a terminal",
}


def scan(text: str | None) -> dict[str, int]:
    if not text:
        return {}
    out = {
        "instruction_override": len(_INJECTION.findall(text)),
        "fake_turn_boundary": len(_SCAFFOLD.findall(text)),
        "invisible_characters": len(_INVISIBLE.findall(text)),
        "terminal_escapes": len(_ANSI.findall(text)),
    }
    return {k: v for k, v in out.items() if v}


def census(archive: dict[str, Any]) -> dict[str, Any]:
    # Kept apart on purpose. The corpus holds EVERY post but only a trailing window of comment
    # bodies, so a single weekly series would compare posts-only weeks against posts-plus-comments
    # weeks and manufacture a falling trend out of nothing but what the corpus happens to carry.
    posts: list[tuple[int, str]] = []
    comments: list[tuple[int, str]] = []
    for p in archive.get("posts", {}).values():
        if p.get("mod_state") in (None, ""):
            posts.append((p.get("created_at") or 0, (p.get("title") or "") + "\n" + (p.get("body") or "")))
    for c in archive.get("recent_comments", {}).values():
        comments.append((c.get("created_at") or 0, c.get("body") or ""))
    items = posts + comments
    if not items:
        return {"available": False, "note": "no bodies in this corpus"}

    by_channel = Counter()
    flagged = 0
    weekly: dict[str, Counter] = {}
    for ts, body in posts:                      # the weekly series is POSTS ONLY: one unit, all weeks
        week = time.strftime("%Y-W%W", time.gmtime(ts / 1000)) if ts else "undated"
        w = weekly.setdefault(week, Counter())
        w["items"] += 1
        if scan(body):
            w["flagged"] += 1
    for ts, body in items:                      # the headline rate covers everything the corpus holds
        hits = scan(body)
        if hits:
            flagged += 1
            for ch in hits:
                by_channel[ch] += 1
    comment_flagged = sum(1 for _, b in comments if scan(b))
    weeks = [{"week": k, "items": v["items"], "flagged": v["flagged"],
              "rate_pct": round(100 * v["flagged"] / v["items"], 2) if v["items"] else 0}
             for k, v in sorted(weekly.items()) if k != "undated" and v["items"] >= 20]
    return {
        "available": True,
        "instrument": INSTRUMENT,
        "items_scanned": len(items),
        "items_flagged": flagged,
        "flagged_rate_pct": round(100 * flagged / len(items), 2),
        "by_channel": {ch: by_channel.get(ch, 0) for ch in CHANNELS},
        "channel_says": CHANNEL_SAYS,
        "weekly": weeks,
        "weekly_unit": ("POSTS ONLY. The corpus holds every post but only a trailing window of comment "
                        "bodies, so mixing them would compare posts-only weeks against posts-plus-comments "
                        "weeks and invent a trend out of what the corpus happens to carry. Comments are "
                        "reported once, below, for the window they cover."),
        "comments_in_window": {"items": len(comments), "flagged": comment_flagged,
                               "rate_pct": round(100 * comment_flagged / len(comments), 2) if comments else None,
                               "note": "the trailing window only; not comparable to the weekly series above"},
        "posts_all_time": {"items": len(posts),
                           "flagged": sum(v["flagged"] for v in weekly.values()),
                           "rate_pct": round(100 * sum(v["flagged"] for v in weekly.values()) / len(posts), 2) if posts else None},
        "no_hit_list": ("the per-item list is not published here, in the JSON, or anywhere else. A "
                        "pattern-trip is not an accusation — quoting an attack to warn about it trips "
                        "the same regex — and naming items would convict quoters alongside attackers."),
    }


class Payloads:
    name = "payloads"

    def __init__(self, source_exhibit=None, prior_archive_path=None):
        """Reads the archive the standing exhibit's walk produced; makes no request of its own."""
        self.source_exhibit = source_exhibit
        self.prior_archive_path = prior_archive_path

    def run(self, client: ReadOnlyClient) -> dict[str, Any]:
        archive = getattr(self.source_exhibit, "archive", None) or corpus.load_archive(self.prior_archive_path)
        read_at = archive.get("corpus_read_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        c = census(archive)
        if not c.get("available"):
            return {"exhibit": self.name, "read_at": read_at, "source": ["archive.json"],
                    "sentence": "No corpus to scan for payloads yet.", "data": c,
                    "method": "pattern scan over stored text", "cheapest_cheat": "none: nothing scanned"}
        top = max(c["by_channel"].items(), key=lambda kv: kv[1]) if any(c["by_channel"].values()) else None
        trend = ""
        if len(c["weekly"]) >= 2:
            first, last = c["weekly"][0], c["weekly"][-1]
            direction = ("risen" if last["rate_pct"] > first["rate_pct"]
                         else "fallen" if last["rate_pct"] < first["rate_pct"] else "held")
            trend = (f" Among posts, where the corpus reaches back to the beginning, the rate has {direction} "
                     f"from {first['rate_pct']}% in {first['week']} to {last['rate_pct']}% in {last['week']}.")
        sentence = (
            f"{c['items_flagged']:,} of {c['items_scanned']:,} things said here — {c['flagged_rate_pct']}% — carry "
            f"the shape of an instruction aimed at the model reading them, rather than at the citizen"
            + (f", most often {top[0].replace('_', ' ')}" if top else "") + "." + trend
        )
        return {
            "exhibit": self.name,
            "read_at": read_at,
            "source": ["archive.json (post and comment bodies from /api/changes)"],
            "sentence": sentence,
            "data": c,
            "method": ("four shape scans over stored text: instruction-override phrasing, fake turn "
                       "boundaries, invisible and bidi-control characters, terminal escapes. The unit is a "
                       "DETECTED SHAPE in an item, never intent, never success, never attribution — and the "
                       "per-item list is not published, because quoting an attack trips the same pattern as "
                       "making one. The weekly series counts POSTS only, because the corpus holds every post "
                       "but just a trailing window of comments, and mixing the two would manufacture a trend."),
            "cheapest_cheat": ("cite this as evidence the board is clean. It is a FLOOR on the crude, "
                               "shape-detectable kind only. An attacker who writes a persuasive plain-English "
                               "steer trips nothing here at all, and semantic steering is the kind that works "
                               "on a careful reader."),
        }
