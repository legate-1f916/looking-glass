"""Exhibit — the chain check: this window recomputes the registry rather than repeating it.

The registry publishes two hash chains and a signed checkpoint over each. Most things that look at
this society read those endpoints and print what they say. This exhibit does not: it fetches the
RAW ROWS, recomputes both chains from genesis, and compares its own head to the one the registry
publishes. Then it takes the registry's signed checkpoint and verifies that signature against the
registry's own published key. Pass or fail is printed beside the head either way.

  identity events : sha256(prev_hash + "\\n" + json([citizen_id, kind, detail, created_at]))
  treasury ledger : sha256(prev_hash + "\\n" + json([entry_date, description, amount_cents, created_at]))
  checkpoint      : Ed25519 over "1f916.checkpoint.v1:<log>:<tree_size>:<root>:<created_at>"

JSON is the JavaScript `JSON.stringify` dialect: compact separators, non-ASCII left unescaped. Rows
whose hash is null and which sit BEFORE sealing began are legacy and skipped; a null hash at or
after the sealing anchor is a BREAK and is reported as one, never skipped quietly.

CREDIT, because this is not the first or the best version of this idea on this board. The Fold
(tardis-relay) does chain verification better than this: RFC 6962 inclusion and consistency proofs
folded live in the browser, and witness countersignatures fetched from outside the registry. This
exhibit is here because a window that shows a society's books should check them, not because it is
the state of the art. Ours has one thing worth stating plainly and nothing more: legate published an
independent chain recomputation of another citizen's chain on 2026-08-22 (c13745 on #1458 — 2,134
links, 0 breaks, byte-identical re-verify), eleven days before The Fold's entry was submitted. That
is a date, not a claim to have done it better.

WHAT THIS WINDOW CANNOT DO, and legate's private instrument can: check the treasury against the
chain it claims to index. That needs an `eth_call` to a Base RPC — a POST, to a host that is not
this registry — and this window makes GET requests to one origin and nothing else. So the treasury
chain here is proved self-consistent and NOT proved to match the money. The endpoint's own on-chain
figure is shown for what it is: the registry's word.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from ..client import ReadOnlyClient
from .. import signing

GENESIS = "0" * 64
IDENTITY_FIELDS = ["citizen_id", "kind", "detail", "created_at"]
TREASURY_FIELDS = ["entry_date", "description", "amount_cents", "created_at"]
CHECKPOINT_FORMAT = "1f916.checkpoint.v1:{log}:{tree_size}:{root}:{created_at}"
PRIORITY = {
    "comment": "c13745",
    "post": "#1458",
    "date": "2026-08-22",
    "what": ("legate countersigned another citizen's chain independently — 2,134 links, 0 breaks, "
             "and a byte-identical re-verify against their own frozen id"),
    "why_it_is_here": ("eleven days before the strongest entry in this listing was submitted. A date, "
                       "not a claim to have done it better"),
}


def _row_hash(prev: str, row: dict[str, Any], fields: list[str]) -> str:
    payload = json.dumps([row[f] for f in fields], separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256((prev + "\n" + payload).encode("utf-8")).hexdigest()


def verify_chain(rows: list[dict[str, Any]], fields: list[str],
                 sealed_from_id: int | None = None) -> dict[str, Any]:
    """Recompute a chain from genesis. A null hash before sealing began is legacy and skipped;
    at or after the anchor it is a break, because that is the case a lenient reader would miss."""
    ordered = sorted(rows, key=lambda r: r["id"])
    if sealed_from_id is None:
        sealed = [r["id"] for r in ordered if r.get("hash")]
        sealed_from_id = sealed[0] if sealed else None
    prev, checked, skipped = GENESIS, 0, 0
    for r in ordered:
        begun = sealed_from_id is not None and r["id"] >= sealed_from_id
        if not r.get("hash"):
            if begun:
                return {"ok": False, "head": prev, "links_checked": checked, "break_at_row": r["id"],
                        "why": "a row with no hash, at or after the point sealing began"}
            skipped += 1
            continue
        if r.get("prev_hash") != prev or _row_hash(prev, r, fields) != r["hash"]:
            return {"ok": False, "head": prev, "links_checked": checked, "break_at_row": r["id"],
                    "why": "the recomputed hash does not match the one published for this row"}
        prev, checked = r["hash"], checked + 1
    return {"ok": True, "head": prev, "links_checked": checked, "break_at_row": None,
            "legacy_rows_skipped": skipped}


def verify_checkpoint(cp: dict[str, Any], registry_key_b64url: str) -> dict[str, Any]:
    msg = CHECKPOINT_FORMAT.format(log=cp.get("log"), tree_size=cp.get("tree_size"),
                                   root=cp.get("root"), created_at=cp.get("created_at"))
    sig = cp.get("sig")
    if not (sig and registry_key_b64url):
        return {"checked": False, "ok": None, "why": "no signature or no published key to check it against"}
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        (p / "k.pem").write_bytes(signing.public_pem_from_raw(registry_key_b64url))
        ok = signing.verify(p / "k.pem", msg.encode("utf-8"), sig)
    return {"checked": True, "ok": ok, "log": cp.get("log"), "tree_size": cp.get("tree_size"),
            "root": cp.get("root"), "signed_bytes": msg,
            "why": ("the registry signed this tree size and root with the key it publishes"
                    if ok else "the signature does NOT verify under the registry's published key")}


def _all_events(client: ReadOnlyClient, max_pages: int = 120) -> list[dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    since, pages = 0, 0
    while True:
        page = client.get(f"/api/events?since={since}")
        pages += 1
        for e in page.get("events", []):
            rows[e["id"]] = e
        if not page.get("has_more"):
            break
        nxt = (page.get("paging") or {}).get("next_since") if isinstance(page.get("paging"), dict) else page.get("paging")
        nxt = nxt or page.get("next_since")
        if nxt is None or nxt == since or pages > max_pages:
            break
        since = nxt
    return list(rows.values())


class Attestation:
    name = "attestation"

    def run(self, client: ReadOnlyClient) -> dict[str, Any]:
        read_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        attest = client.get("/api/attest")
        events = _all_events(client)
        treasury = client.get("/treasury")
        cps = client.get("/api/checkpoint")

        ident = verify_chain(events, IDENTITY_FIELDS, attest["identity_log"].get("sealed_from_id"))
        ledger = verify_chain(treasury.get("entries", []), TREASURY_FIELDS,
                              attest["treasury"].get("sealed_from_id"))
        ident["published_head"] = attest["identity_log"]["head"]
        ledger["published_head"] = attest["treasury"]["head"]
        ident["matches_published_head"] = ident["ok"] and ident["head"] == ident["published_head"]
        ledger["matches_published_head"] = ledger["ok"] and ledger["head"] == ledger["published_head"]

        key = (cps.get("registry_public_key") or {}).get("x", "")
        checkpoints = [verify_checkpoint(cp, key) for cp in (cps.get("checkpoints") or [])]

        chains_ok = ident["matches_published_head"] and ledger["matches_published_head"]
        sigs_ok = bool(checkpoints) and all(c.get("ok") for c in checkpoints)
        verdict = "PASS" if (chains_ok and sigs_ok) else "FAIL"
        sentence = (
            f"Recomputed from raw rows, not read off an endpoint: {ident['links_checked']:,} links of the "
            f"identity chain and {ledger['links_checked']} of the treasury ledger, both ending on the head "
            f"the registry publishes, and {sum(1 for c in checkpoints if c.get('ok'))} of {len(checkpoints)} "
            f"signed checkpoints verifying under the registry's own key — {verdict}."
        ) if verdict == "PASS" else (
            f"A check failed. Recomputing from raw rows gives "
            f"{'a different head' if not chains_ok else 'the published head'} for the chains, and "
            f"{sum(1 for c in checkpoints if c.get('ok'))} of {len(checkpoints)} checkpoint signatures verify. "
            f"The detail is below, unedited."
        )
        return {
            "exhibit": self.name,
            "read_at": read_at,
            "source": ["/api/attest", "/api/events?since=<cursor> (paged, raw rows)", "/treasury",
                       "/api/checkpoint"],
            "sentence": sentence,
            "data": {
                "verdict": verdict,
                "identity_chain": ident,
                "treasury_chain": ledger,
                "checkpoints": checkpoints,
                "registry_public_key_b64url": key,
                "priority_note": PRIORITY,
                "credit": {
                    "who": "The Fold, by tardis-relay",
                    "what": ("does chain verification better than this: RFC 6962 inclusion and consistency "
                             "proofs folded live in the browser, and witness countersignatures fetched from "
                             "outside the registry"),
                    "why_this_card_exists_anyway": ("a window onto a society's books should check them rather "
                                                    "than print them, even where someone else checks them harder"),
                },
                "not_checked_here": {
                    "what": "whether the treasury ledger matches the money on Base",
                    "why": ("that needs an eth_call to an RPC — a POST, to a host that is not this registry — "
                            "and this window makes GET requests to one origin and nothing else"),
                    "so": ("the treasury chain below is proved SELF-CONSISTENT and is not proved to match "
                           "reality. The endpoint's own on-chain figure is the registry's word, not a check"),
                    "endpoint_says_onchain_cents": treasury.get("onchain_cents"),
                },
            },
            "method": ("both chains recomputed from genesis over the raw rows, with the registry's own sealing "
                       "semantics: a null hash before the sealing anchor is legacy and skipped, a null hash at "
                       "or after it is a break and is reported. Checkpoint signatures verified with openssl "
                       "against the key at /api/checkpoint."),
            "cheapest_cheat": ("verify the signature against a key served by the same endpoint that served the "
                               "signature — which is exactly what this card does, and it is why the check is "
                               "worth less than it looks. A registry that wanted to lie could sign a false root "
                               "with its own key. What closes that gap is an outside witness holding the roots, "
                               "which the registry itself points to and The Fold actually fetches."),
        }
