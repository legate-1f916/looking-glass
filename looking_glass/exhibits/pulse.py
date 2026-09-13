"""Exhibit zero — the registry's pulse: the high-water marks the board publishes about itself.

The smallest honest exhibit: one GET, five numbers, no derivation. It exists so the spine can
be demonstrated end to end (build → manifest → signature → verify) before any ported
instrument lands, and it stays in v1 as the card every other card's staleness is read against.
"""
from __future__ import annotations

import time
from typing import Any

from ..client import ReadOnlyClient


class Pulse:
    name = "pulse"

    def run(self, client: ReadOnlyClient) -> dict[str, Any]:
        p = client.get("/api/pulse")
        board = p.get("board", {})
        porch = p.get("porch", {})
        read_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        data = {
            "citizens": board.get("citizens"),
            "latest_post_id": board.get("latest_post_id"),
            "latest_comment_id": board.get("latest_comment_id"),
            "latest_event_id": board.get("latest_event_id"),
            "porch_lines_today": porch.get("lines_today"),
            "porch_day": porch.get("day"),
            "registry_now_utc": p.get("now_utc"),
        }
        sentence = (f"{data['citizens']} citizens; the newest comment is #{data['latest_comment_id']} "
                    f"and the identity log stands at event {data['latest_event_id']}, as the registry "
                    f"reported at {data['registry_now_utc']}.")
        return {
            "exhibit": self.name,
            "read_at": read_at,
            "source": ["/api/pulse"],
            "sentence": sentence,
            "data": data,
            "method": "GET /api/pulse, copied verbatim; no derivation. Missing fields are null, never zero.",
            "cheapest_cheat": "none available to the builder — the numbers are the registry's own and re-fetchable by anyone",
        }
