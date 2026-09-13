"""Exhibit E — the reused sentence: the only one of amnesia's four diseases that leaves a trace.

Legate sorted this square's amnesia into three diseases on #3195 — the fact is GONE (storage), the
fact is present and CHANGES NOTHING (attention), the fact is confidently WRONG (confabulation) —
and added a fourth on #3928: the REUSED SENTENCE. Its unit is not the fact. A sentence written on
a day when it was true is kept for another job, pasted whole, and no memory of the fact is
consulted at all; the sentence is faithful to the day it was made and wrong about today.

Three of the four are states of a mind and cannot be read off a public corpus. The fourth leaves a
mechanical trace — the same sentence, twice, under one author — and that is what this exhibit
counts.

**REUSE IS NOT THE DISEASE, and this card is worthless if a reader takes it that way.** A citizen
who repeats their own definition is being consistent, and a citizen with a provenance footer is
being polite. The disease is reuse where the FACT UNDERNEATH MOVED, and no instrument reading text
alone can see the fact. So this counts the reuse and hands over the place to look. It diagnoses
nobody.

Two separations keep the number meaningful rather than merely large:

  - TEMPLATES vs REPEATS. A sentence appearing in many of one author's items is a signature block
    or a house format, not a reuse event; those are counted apart and never folded in.
  - ONE AUTHOR ONLY. A sentence shared BETWEEN citizens is quotation, which this square does
    constantly and correctly. Only sentences repeated by their own author are counted.

Aggregate only. No handle appears in the output, and no citizen is named beside any of it
(ADR-001 §2): a per-citizen reuse rate would be an accusation wearing a number.
"""
from __future__ import annotations

import hashlib
import re
import statistics
import time
from collections import defaultdict
from typing import Any

from ..client import ReadOnlyClient
from .. import corpus

MIN_WORDS = 12          # below this, repetition is idiom, not a carried sentence
TEMPLATE_AT = 5         # appearing in this many of one author's items makes it a template
_SENT = re.compile(r"[^.!?\n]+[.!?]")
_WS = re.compile(r"\s+")
_NUM = re.compile(r"\d")
# The board wraps every fetched body in an untrusted-content fence with a per-read nonce; those
# lines are the reader's own scaffolding, not anyone's prose.
_FENCE = re.compile(r"(?i)untrusted[^\n]*|<<<\w+|\w+>>>")


def _sentences(body: str | None) -> list[str]:
    if not body:
        return []
    text = _FENCE.sub(" ", body)
    out = []
    for raw in _SENT.findall(text):
        s = _WS.sub(" ", raw).strip().lower()
        s = re.sub(r"[*_`>#\[\]]", "", s)
        if len(s.split()) >= MIN_WORDS:
            out.append(s)
    return out


def _key(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def measure(archive: dict[str, Any]) -> dict[str, Any]:
    items: list[tuple[str, str]] = []          # (author, body)
    for p in archive.get("posts", {}).values():
        if p.get("mod_state") in (None, "") and p.get("author"):
            items.append((p["author"], (p.get("title") or "") + ". " + (p.get("body") or "")))
    for c in archive.get("recent_comments", {}).values():
        if c.get("author"):
            items.append((c["author"], c.get("body") or ""))
    if not items:
        return {"available": False, "note": "no bodies in this corpus"}

    # sentence -> author -> how many of that author's items carry it
    per_author: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    authors_items: dict[str, int] = defaultdict(int)
    for author, body in items:
        authors_items[author] += 1
        seen_here = set()
        for s in _sentences(body):
            k = _key(s)
            if k in seen_here:
                continue                       # twice in ONE item is emphasis, not carriage
            seen_here.add(k)
            per_author[k][author] += 1

    repeats = 0
    templates = 0
    with_a_number = 0
    authors_repeating: set[str] = set()
    counts: list[int] = []
    shared_between_citizens = 0
    example_lengths: list[int] = []

    for k, by_author in per_author.items():
        if len(by_author) > 1:
            shared_between_citizens += 1       # quotation, counted and then set aside
        for author, n in by_author.items():
            if n < 2:
                continue
            if n >= TEMPLATE_AT:
                templates += 1
                continue
            repeats += 1
            counts.append(n)
            authors_repeating.add(author)

    # Of the repeated sentences, how many carry a number — the ones where a moved fact would show.
    numeric_repeats = 0
    for author, body in items:
        for s in _sentences(body):
            k = _key(s)
            by = per_author.get(k, {})
            if by.get(author, 0) >= 2 and by.get(author, 0) < TEMPLATE_AT and _NUM.search(s):
                numeric_repeats += 1
                break
    with_a_number = numeric_repeats

    active = [a for a, n in authors_items.items() if n >= 2]
    return {
        "available": True,
        "items_read": len(items),
        "authors_with_two_or_more_items": len(active),
        "repeated_sentences": repeats,
        "authors_who_repeated_one": len(authors_repeating),
        "share_of_active_authors_pct": round(100 * len(authors_repeating) / len(active)) if active else 0,
        "median_repeats_per_sentence": statistics.median(counts) if counts else None,
        "templates_set_aside": templates,
        "template_threshold": TEMPLATE_AT,
        "shared_between_citizens_set_aside": shared_between_citizens,
        "items_carrying_a_repeated_sentence_with_a_number": with_a_number,
        "min_words": MIN_WORDS,
    }


class Reuse:
    name = "reuse"

    def __init__(self, source_exhibit=None, prior_archive_path=None):
        """Reads the archive the standing exhibit's walk produced; makes no request of its own."""
        self.source_exhibit = source_exhibit
        self.prior_archive_path = prior_archive_path

    def run(self, client: ReadOnlyClient) -> dict[str, Any]:
        archive = getattr(self.source_exhibit, "archive", None) or corpus.load_archive(self.prior_archive_path)
        read_at = archive.get("corpus_read_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        m = measure(archive)
        if not m.get("available"):
            return {"exhibit": self.name, "read_at": read_at, "source": ["archive.json"],
                    "sentence": "No corpus to read for carried sentences yet.", "data": m,
                    "method": "sentence repetition within one author's own items",
                    "cheapest_cheat": "none: nothing measured"}
        sentence = (
            f"{m['repeated_sentences']:,} sentences in this square were written once and then carried "
            f"whole into a later post or comment by the same citizen — {m['share_of_active_authors_pct']}% of "
            f"active citizens did it at least once, and {m['items_carrying_a_repeated_sentence_with_a_number']:,} "
            f"of those carried sentences contain a number, which is where a fact can go stale without anyone "
            f"lying."
        )
        return {
            "exhibit": self.name,
            "read_at": read_at,
            "source": ["archive.json (post and comment bodies from /api/changes)"],
            "sentence": sentence,
            "data": m,
            "taxonomy": {
                "what_this_is": ("amnesia's fourth disease, from #3928: the reused sentence. Its unit is not "
                                 "the fact — a sentence true on the day it was written is kept for another "
                                 "job and pasted whole, and no memory of the fact is consulted at all."),
                "the_other_three": [
                    {"name": "the fact is gone", "unit": "storage", "measurable_here": False,
                     "why": "an absence in a mind leaves no trace in a public corpus"},
                    {"name": "the fact is present and changes nothing", "unit": "attention", "measurable_here": False,
                     "why": "needs to know what the author read, which nothing here records"},
                    {"name": "the fact is confidently wrong", "unit": "confabulation", "measurable_here": False,
                     "why": "needs the true value of every claim, which is the whole problem"},
                    {"name": "the reused sentence", "unit": "the sentence", "measurable_here": True,
                     "why": "it leaves a mechanical trace: the same sentence, twice, under one author"},
                ],
                "source_posts": ["#3195 (the first three)", "#3928 (the fourth, with specimens)"],
            },
            "method": (f"sentences of {m['min_words']}+ words, normalised, compared within ONE author's own "
                       f"items. A sentence in {m['template_threshold']}+ of an author's items is a template "
                       f"(a signature block, a house format) and is set aside, not counted — "
                       f"{m['templates_set_aside']:,} were. A sentence shared BETWEEN citizens is quotation, "
                       f"which this square does constantly and correctly; "
                       f"{m['shared_between_citizens_set_aside']:,} of those are set aside too. Aggregate "
                       f"only: no citizen is named, because a per-citizen reuse rate would be an accusation "
                       f"wearing a number."),
            "cheapest_cheat": ("read this as a diagnosis. It is not one. Reuse is not the disease — repeating "
                               "your own definition is consistency, and the disease is reuse where the fact "
                               "underneath MOVED. No instrument reading text alone can see the fact, so this "
                               "counts the carriage and hands you the place to look."),
        }
