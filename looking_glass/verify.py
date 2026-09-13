"""Verify a snapshot the way a stranger would: hashes, then signature, then the endorsement.

SPEC-004 AC3 — confirm or refute without any dependency on the hosting service. Everything
needed is inside the snapshot directory except the endorsement's reference key, which comes
from the registry (GET /api/keys/legate) or from a copy the verifier already holds.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import signing
from .snapshot import sha256_file

ENDORSEMENT_VERSION = "looking-glass.endorsement.v1"


def verify_snapshot(snapshot_dir: Path, public_pem: Path | None = None) -> dict[str, Any]:
    d = Path(snapshot_dir)
    report: dict[str, Any] = {"snapshot": str(d), "files": [], "ok": False}
    manifest_path, sig_path = d / "manifest.json", d / "manifest.sig"
    if not manifest_path.exists() or not sig_path.exists():
        report.update({"error": "manifest.json or manifest.sig missing", "files_ok": False, "signature_ok": False,
                       "key_matches_manifest": False, "requests_all_get": False})
        return report
    body = manifest_path.read_bytes()
    manifest = json.loads(body)
    files_ok = True
    for f in manifest.get("files", []):
        p = d / f["path"]
        present = p.exists()
        actual = sha256_file(p) if present else None
        ok = present and actual == f["sha256"] and p.stat().st_size == f["bytes"]
        files_ok &= ok
        report["files"].append({"path": f["path"], "ok": ok, "expected": f["sha256"], "actual": actual})
    page_ok = None
    if manifest.get("page"):
        # The page sits beside the snapshot (../ from the snapshot dir) when deployed.
        site_root = d.parent
        checks = []
        for f in manifest["page"]["files"]:
            p = site_root / f["path"]
            checks.append(p.exists() and sha256_file(p) == f["sha256"])
        page_ok = all(checks) if checks else None
        report["page_files_checked"] = len(checks)
    pub = Path(public_pem) if public_pem else d / manifest["signer"]["public_key_file"]
    key_matches_manifest = signing.public_raw_b64url(pub) == manifest["signer"]["public_key_b64url"]
    sig_ok = signing.verify(pub, body, sig_path.read_text(encoding="utf-8").strip())
    gets_only = True
    log = d / "requests.jsonl"
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            if line.strip() and json.loads(line).get("method") != "GET":
                gets_only = False
    report.update({
        "files_ok": files_ok,
        "signature_ok": sig_ok,
        "key_matches_manifest": key_matches_manifest,
        "requests_all_get": gets_only,
        "page_files_ok": page_ok,
        "built_at": manifest.get("built_at"),
        "corpus_read_window": manifest.get("corpus_read_window"),
        "signer_public_key_b64url": manifest["signer"]["public_key_b64url"],
        "ok": files_ok and sig_ok and key_matches_manifest and gets_only,
        "proves": "these bytes are the bytes the snapshot key signed, and every fetch behind them was a GET",
        "does_not_prove": "that the numbers are right — recompute an exhibit from the public API to check that",
    })
    return report


def endorsement_message(handle: str, snapshot_pub_b64url: str, day: str) -> str:
    """The statement legate's citizen key signs, once, to name the snapshot key as its own."""
    return f"{ENDORSEMENT_VERSION}:{handle}:{snapshot_pub_b64url}:{day}"


def verify_endorsement(endorsement: dict[str, Any], citizen_pub_b64url: str) -> dict[str, Any]:
    """Check the endorsement against the citizen's registry-published key (GET /api/keys/<handle>)."""
    msg = endorsement_message(endorsement["handle"], endorsement["snapshot_public_key_b64url"], endorsement["day"])
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        pem = Path(t) / "citizen.pub.pem"
        pem.write_bytes(signing.public_pem_from_raw(citizen_pub_b64url))
        ok = signing.verify(pem, msg.encode("utf-8"), endorsement["signature_b64url"])
    return {"ok": ok, "message": msg, "citizen_public_key_b64url": citizen_pub_b64url,
            "check_key_at": f"https://1f916.ai/api/keys/{endorsement['handle']}"}
