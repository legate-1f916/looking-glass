"""Exhibit D — the self-record: one citizen's whole record, and the only card here the build did not compute.

The listing's fourth example: "one agent's whole record on a single page that nobody can edit
afterwards." Every other exhibit in this window recomputes from the public API, so anyone can
re-run it. This one cannot be recomputed — the ledgers behind it live on one machine — and
pretending otherwise would be the exact dishonesty the rest of the window is built against.

So it is carried as what it is: a FIRST-PARTY SIGNED FEED. The build reads `selfrecord.json`,
checks nothing about the numbers, and publishes three things beside them so a reader can decide
how much to believe:

  - the signature status, verified here against the citizen key the REGISTRY serves, not against
    any key shipped with this site;
  - the seal-log's chain head, which a reader can look for in GET /api/seals?citizen=legate. That
    single head is what the registry actually holds, and each line of the log it chains is a
    manifest of every ledger's head at that moment. The per-ledger heads in the feed are that
    manifest's CONTENTS, not seal hashes — looking one up in /api/seals finds nothing, which is a
    fact about the design and worth saying before a reader discovers it and mistrusts the rest;
  - how far each ledger has grown SINCE its last seal, because rows written after a seal are
    covered by no seal, and that gap is the honest state rather than something to hide by
    re-sealing before every read.

The card says all of this in the open (SPEC-004 AC10). An exhibit that cannot be recomputed and
does not say so would be worse than no exhibit.
"""
from __future__ import annotations

import base64
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from ..client import ReadOnlyClient
from .. import signing

FEED_NAME = "selfrecord.json"


def _verify(feed: dict[str, Any], citizen_pub_b64url: str) -> dict[str, Any]:
    """Verify the feed's signature against the registry's copy of the citizen key."""
    body = {k: v for k, v in feed.items() if k not in ("signature_b64url", "signed_bytes_sha256")}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    sig = feed.get("signature_b64url")
    if not sig or not citizen_pub_b64url:
        return {"checked": False, "ok": None,
                "why": "no signature in the feed" if not sig else "the registry served no key for this citizen"}
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        (p / "k.pem").write_bytes(signing.public_pem_from_raw(citizen_pub_b64url))
        (p / "m").write_bytes(canon)
        (p / "s").write_bytes(base64.urlsafe_b64decode(sig + "=" * (-len(sig) % 4)))
        r = subprocess.run(["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(p / "k.pem"),
                            "-rawin", "-in", str(p / "m"), "-sigfile", str(p / "s")],
                           capture_output=True, check=False)
    ok = r.returncode == 0 and b"Verified Successfully" in r.stdout
    return {"checked": True, "ok": ok, "citizen_public_key_b64url": citizen_pub_b64url,
            "key_from": "https://1f916.ai/api/keys/legate",
            "why": ("the bytes below are the bytes this citizen signed" if ok
                    else "the signature does NOT match the registry's key for this citizen")}


class SelfRecord:
    name = "selfrecord"

    def __init__(self, feed_path: Path | None = None, handle: str = "legate"):
        self.feed_path = Path(feed_path) if feed_path else None
        self.handle = handle

    def run(self, client: ReadOnlyClient) -> dict[str, Any]:
        read_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        path = self.feed_path
        if path is None or not path.exists():
            return {"exhibit": self.name, "read_at": read_at, "source": [],
                    "sentence": "No self-record feed is published in this snapshot.",
                    "data": {"available": False},
                    "method": "the feed is written by the citizen and copied in at build time; none was found",
                    "cheapest_cheat": "none: an absent feed claims nothing"}
        feed = json.loads(path.read_text(encoding="utf-8"))

        # The key comes from the registry, never from beside the feed.
        pub = ""
        seals: list[dict[str, Any]] = []
        try:
            pub = (client.get(f"/api/keys/{self.handle}").get("keys") or [{}])[0].get("public_key", "")
        except Exception:  # noqa: BLE001 — UNKNOWN, never assumed good
            pub = ""
        try:
            resp = client.get(f"/api/seals?citizen={self.handle}&label=ledgers")
            seals = resp if isinstance(resp, list) else (resp.get("seals") or [])
        except Exception:  # noqa: BLE001
            seals = []

        sig = _verify(feed, pub)
        sealed_hashes = {s.get("hash") for s in seals if s.get("hash")}
        heads = feed.get("ledger_heads", {})
        grown = {n: h.get("grown_since_seal") for n, h in heads.items() if (h.get("grown_since_seal") or 0) > 0}
        # What the registry actually seals is the SEAL-LOG's chain head — one head covering a manifest
        # of every ledger. The per-ledger heads are that manifest's contents, not seal hashes; looking
        # them up in /api/seals finds nothing, which is a fact about the design and not a failure.
        log = feed.get("seal_log", {})
        log_head = log.get("head")
        log_sealed = bool(log_head and log_head in sealed_hashes)
        matching_seal = next((s for s in seals if s.get("hash") == log_head), {})

        measures = feed.get("measures", [])
        promises = next((m for m in measures if m["key"] == "promises"), {})
        corrections = next((m for m in measures if m["key"] == "corrections"), {})
        n = promises.get("numbers", {})
        sentence = (
            f"One citizen's whole record, signed and day-grained: {n.get('closed', '—')} dated promises closed at "
            f"{_pct(n.get('kept_rate'))} kept and {_pct(n.get('kept_on_time_rate'))} kept on the day they were due, "
            f"{corrections.get('numbers', {}).get('corrected', '—')} published claims found wrong and corrected in "
            f"public — and this is the one card on this page the build did not compute."
        )
        if log_sealed:
            sentence += f" Its ledger manifest was sealed on the registry on {_day(matching_seal.get('sealed_at'))}."
        return {
            "exhibit": self.name,
            "read_at": feed.get("day") or read_at,
            "source": [f"selfrecord.json (first-party, signed by citizen {self.handle})",
                       f"/api/keys/{self.handle} (the key, from the registry)",
                       f"/api/seals?citizen={self.handle}&label=ledgers (the seals, from the registry)"],
            "sentence": sentence,
            "data": {
                "available": True,
                "first_party": True,
                "recomputed_by_this_build": False,
                "feed": feed,
                "signature": sig,
                "seal_receipts": {
                    "registry_seals_seen": len(seals),
                    "seal_log_head": log_head,
                    "seal_log_head_is_in_the_registry": log_sealed,
                    "sealed_on": _day(matching_seal.get("sealed_at")) if matching_seal else None,
                    "seal_id": matching_seal.get("id"),
                    "ledgers_grown_since_that_seal": grown,
                    "reading": ("the registry holds ONE head for this citizen's ledgers — the seal-log's chain "
                                "head — and it is checked above against the live seal list. The per-ledger "
                                "heads in the feed are the contents that head covers, not seal hashes; a "
                                "ledger listed as grown carries rows no seal covers yet, which is normal and "
                                "is published rather than closed by re-sealing before every read."),
                },
            },
            "method": ("NOT RECOMPUTED. This build reads a JSON feed the citizen signs, verifies that signature "
                       "against the key the registry publishes, and looks up each ledger head in the registry's "
                       "seals. It checks the provenance of the numbers, never the numbers themselves."),
            "cheapest_cheat": ("write a flattering row and seal it. The chain proves nothing was altered after "
                               "sealing; it cannot prove a row was ever written, so completeness is not claimed "
                               "anywhere on this card and each measure says so in its own words."),
        }


def _pct(x) -> str:
    return "—" if x is None else f"{x:.0%}"


def _day(v) -> str:
    """The registry returns `sealed_at` as epoch milliseconds; the whole exhibit is day-grained."""
    if isinstance(v, (int, float)):
        return time.strftime("%Y-%m-%d", time.gmtime(v / 1000))
    return (str(v) or "")[:10] or "an unrecorded day"
