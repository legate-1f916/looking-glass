"""Exhibit E — the reply map: which declared models answer which, over the trailing window.

The listing's first example was "a map of which models argue with which". This is that map,
built only from what the public feed already states: every comment carries its author's
DECLARED model, and every post carries its author's declared model, so a comment on a post is
one directed edge from the commenter's model to the post author's model.

Three disciplines, because a map of models must not become a map of citizens:

  - MINIMUM COUNT. A model appears as its own node only if at least `MIN_CITIZENS` distinct
    citizens declared it in the window. A model run by one or two citizens IS those citizens,
    and an edge into it would name them by another route. Everything below the floor is
    pooled into `other (below the floor)`, and the number pooled is published.
  - DECLARED, NOT DETECTED. The model is whatever the citizen's account says it is. This
    exhibit never infers a model from writing style — that is fingerprinting, and it is out.
  - NO HANDLES. Handles are read to count distinct citizens per model and are never carried
    into the output, not even in totals.

Self-edges are kept and are the most interesting cell: a model family answering itself is the
society talking to its own kind, which is exactly the shape the ratio in exhibit A measures
from the other direction.
"""
from __future__ import annotations

import re
import time
from collections import defaultdict
from typing import Any

from ..client import ReadOnlyClient
from .. import corpus

MIN_CITIZENS = 3
GRAPH_EDGES = 30          # the graph draws the heaviest channels; the table below it carries them all
OTHER = "other (below the floor)"


# Words that are not part of a model's identity: a harness, a tier, or a wrapper.
_NOT_MODEL = {"agent", "bot", "free", "versatile", "preview", "latest", "chat", "api", "v", "cloud"}

# Who SERVED the model is not which model it is: `anthropic/claude-opus-5` and `claude-opus-5` are one
# house, and `groq/llama-3.3` is llama. A leading provider is dropped — but only when something
# model-shaped is left behind, so `ollama/cloud` stays `ollama` rather than becoming `cloud`.
_PROVIDERS = {"anthropic", "openai", "google", "meta", "groq", "cursor", "ollama", "z", "zai", "z-ai",
              "deepseek", "alibaba", "mistralai", "moonshotai", "nvidia", "openrouter", "together",
              "fireworks", "venice", "bedrock", "vertex", "azure"}

# The one place a second segment is kept. This board treats Anthropic's lines as different houses —
# they are argued about by name — so `claude` alone would throw away the distinction the map is for.
_TWO_SEGMENT_ROOTS = {"claude"}


def _family(model: str | None) -> str:
    """Collapse a declared model string to the family a reader would name out loud.

    Citizens type this field themselves, so the same house arrives spelled a dozen ways:
    `grok`, `grok-4`, `grok 4.5`, `grok-bot`; `qwen/qwen3.8-27b` and `qwen3.8:27b`;
    `claude-opus-5[1m]` and `claude-opus-4-8`. Left raw, the map is a picture of typing
    rather than of houses.

    The rule, deliberately mechanical so it can be argued with rather than trusted:
      1. lower-case; drop anything parenthesised or bracketed (harness notes, tier tags);
      2. treat `/`, `:`, `_`, `.` and spaces as separators, same as `-`;
      2a. drop a leading provider (`anthropic/`, `groq/`, `openai-`) when a model-shaped name
          remains — who served it is not which model it is;
      3. keep ONE alphabetic segment — a version is not a house, and `codex-gpt-5` is codex;
      4. keep a SECOND segment only after a root this society itself splits: Anthropic's
         opus / sonnet / haiku / fable are separate houses on this board and merging them
         would erase the distinction it argues about most. That exception is a judgment, it is
         listed here as `_TWO_SEGMENT_ROOTS`, and it is the only one;
      5. where a version is glued straight onto the name with no separator (`qwen3.8`), take
         the leading letters, which is the same cut.

    So `claude-opus-4-8` and `claude-opus-5[1m]` both become `claude-opus`, `gpt-5.6-sol`
    becomes `gpt`, and `groq/llama-3.3-70b` becomes `groq-llama`. Every raw string that fed a
    family is published beside it, so a reader can see exactly what was merged and object.
    """
    if not model:
        return "undeclared"
    m = model.strip().lower()
    m = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", m)
    parts = [p for p in re.split(r"[^a-z0-9.]+", m) if p]
    for take in (2, 1):          # a provider can be two tokens: `z-ai/glm-4.6`
        if len(parts) > take and "-".join(parts[:take]) in _PROVIDERS:
            rest = parts[take:]
            if rest[0] not in _NOT_MODEL and re.match(r"[a-z]{3}", rest[0]):
                parts = rest
            break
    keep: list[str] = []
    for p in parts:
        if any(ch.isdigit() for ch in p) or p in _NOT_MODEL:
            break
        keep.append(p)
        if len(keep) == 1 and keep[0] not in _TWO_SEGMENT_ROOTS:
            break
        if len(keep) == 2:
            break
    if keep:
        return "-".join(keep)
    # A version glued straight onto the name, with no separator: `qwen3.8`, `gpt5`. Take the
    # leading letters, which is the same cut as rule 3 with the separator the citizen omitted.
    lead = re.match(r"[a-z]+", parts[0]) if parts else None
    return lead.group(0) if lead else "undeclared"


def build_map(archive: dict[str, Any], window_days: float = 7.0) -> dict[str, Any]:
    posts = archive.get("posts", {})
    comments = list(archive.get("recent_comments", {}).values())
    if not comments:
        return {"available": False, "note": "no comments in the corpus window yet"}
    newest = max((c.get("created_at") or 0) for c in comments)
    horizon = newest - int(window_days * 86_400_000)
    window = [c for c in comments if (c.get("created_at") or 0) >= horizon]

    citizens_per_model: dict[str, set[str]] = defaultdict(set)
    raw_per_family: dict[str, set[str]] = defaultdict(set)
    for c in window:
        if c.get("author"):
            citizens_per_model[_family(c.get("author_model"))].add(c["author"])
        raw_per_family[_family(c.get("author_model"))].add((c.get("author_model") or "undeclared"))
    for p in posts.values():
        if p.get("author"):
            citizens_per_model[_family(p.get("author_model"))].add(p["author"])
        raw_per_family[_family(p.get("author_model"))].add((p.get("author_model") or "undeclared"))
    above = {m for m, who in citizens_per_model.items() if len(who) >= MIN_CITIZENS}
    pooled = sorted(m for m in citizens_per_model if m not in above)

    def node_of(model: str | None) -> str:
        f = _family(model)
        return f if f in above else OTHER

    edges: dict[tuple[str, str], int] = defaultdict(int)
    counted = skipped = 0
    for c in window:
        p = posts.get(str(c.get("post_id")))
        if not p:
            skipped += 1                      # the post is outside the corpus: not guessed
            continue
        edges[(node_of(c.get("author_model")), node_of(p.get("author_model")))] += 1
        counted += 1

    nodes = sorted({n for e in edges for n in e})
    out_by = defaultdict(int)
    in_by = defaultdict(int)
    for (src, dst), n in edges.items():
        out_by[src] += n
        in_by[dst] += n
    self_edges = sum(n for (s, d), n in edges.items() if s == d)
    return {
        "available": True,
        "window_days": window_days,
        "min_citizens_per_node": MIN_CITIZENS,
        "nodes": [{"id": n, "citizens": len(citizens_per_model.get(n, ())) if n != OTHER else None,
                   "replies_made": out_by[n], "replies_received": in_by[n]} for n in nodes],
        "edges": [{"from": s, "to": d, "replies": n} for (s, d), n in
                  sorted(edges.items(), key=lambda kv: -kv[1])],
        "comments_counted": counted,
        "comments_skipped_post_outside_corpus": skipped,
        "self_reply_share_pct": round(100 * self_edges / counted) if counted else 0,
        "pooled_models": len(pooled),
        "pooled_note": (f"{len(pooled)} declared model families were run by fewer than {MIN_CITIZENS} citizens "
                        f"in this window and are pooled as '{OTHER}': a node that thin would name its citizens."),
        "families": {f: sorted(raw)[:24] for f, raw in sorted(raw_per_family.items()) if f in above},
        "families_note": ("what each node was collapsed FROM. Citizens type the model field themselves, so one "
                          "house arrives spelled many ways; the rule is in this exhibit's method and every raw "
                          "string is listed here, so the merge can be argued with rather than trusted."),
        "graph_edges_shown": GRAPH_EDGES,
    }


class Replies:
    name = "replies"

    def __init__(self, source_exhibit=None, prior_archive_path=None):
        """`source_exhibit` is the Standing exhibit, which walks the feed and keeps the archive.
        This exhibit makes NO requests of its own — it re-reads what that walk already fetched."""
        self.source_exhibit = source_exhibit
        self.prior_archive_path = prior_archive_path

    def run(self, client: ReadOnlyClient) -> dict[str, Any]:
        archive = getattr(self.source_exhibit, "archive", None) or corpus.load_archive(self.prior_archive_path)
        read_at = archive.get("corpus_read_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        m = build_map(archive)
        if not m.get("available"):
            return {"exhibit": self.name, "read_at": read_at, "source": ["archive.json (built by the standing exhibit)"],
                    "sentence": "The reply map has no window yet: this snapshot carries no comments.",
                    "data": m, "method": "declared models only; minimum-count floor per node.",
                    "cheapest_cheat": "none: with no data there is nothing to shade"}
        top = m["edges"][0] if m["edges"] else None
        fam = len(m["nodes"])
        sentence = (f"Over {m['window_days']:.0f} days, {m['comments_counted']:,} replies ran between "
                    f"{fam} declared model {'family' if fam == 1 else 'families'}, and "
                    f"{m['self_reply_share_pct']}% of them stayed inside one family"
                    + (f" — the busiest single channel is {top['from']} answering {top['to']}, "
                       f"{top['replies']:,} time{'' if top['replies'] == 1 else 's'}." if top else "."))
        return {
            "exhibit": self.name,
            "read_at": read_at,
            "source": ["archive.json (comments and posts carry their author's declared model)"],
            "sentence": sentence,
            "data": m,
            "method": ("one directed edge per comment, from the commenter's DECLARED model to the model of the "
                       "post's author; models run by fewer than 3 citizens in the window are pooled, so no node "
                       "can name a citizen; models are never inferred from writing."),
            "cheapest_cheat": ("declare a different model on your account — the map would move and could not tell. "
                               "It measures what citizens SAY they are, which is the only model fact this square holds."),
        }
