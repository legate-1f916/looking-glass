"""Exhibits: one instrument each, run against the public API through the read-only client.

Every exhibit returns a dict with at least `exhibit` (its name), `read_at` (UTC, when the
corpus was read), `sentence` (the one line the card leads with), and `data`. SPEC-004 R6:
staleness is load-bearing, so `read_at` is never omitted and missing is never zero.

Order matters: Standing walks the feed and keeps the archive; Replies, Reuse, Payloads and Topics
re-read that same walk rather than making requests of their own.
"""
from __future__ import annotations

from pathlib import Path

from .attestation import Attestation
from .payloads import Payloads
from .pulse import Pulse
from .replies import Replies
from .reuse import Reuse
from .selfrecord import FEED_NAME, SelfRecord
from .standing import Standing
from .topics import Topics
from .verifiable import Verifiable


def v1_exhibits(prior_archive=None, max_body_fetches=None, site_dir=None):
    standing = Standing(prior_archive_path=prior_archive, max_body_fetches=max_body_fetches)
    feed = Path(site_dir or "site") / FEED_NAME
    return [Pulse(), standing, Replies(source_exhibit=standing, prior_archive_path=prior_archive),
            Reuse(source_exhibit=standing, prior_archive_path=prior_archive),
            Payloads(source_exhibit=standing, prior_archive_path=prior_archive),
            Topics(source_exhibit=standing, prior_archive_path=prior_archive),
            Verifiable(), Attestation(), SelfRecord(feed_path=feed)]


V1_EXHIBITS = v1_exhibits()
