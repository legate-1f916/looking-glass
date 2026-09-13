"""Build one snapshot: every exhibit's JSON, the request log, a manifest, and its signature.

A snapshot is the unit a stranger verifies (SPEC-004 AC2). The manifest names every file with
its sha256 and size, the corpus read window (earliest and latest `read_at` across exhibits),
the build time, and the signer's public key. The manifest bytes are canonical JSON and the
signature is over exactly those bytes, so `manifest.json` on disk IS the signed message.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable, Protocol

from . import __version__, signing
from .client import ReadOnlyClient

MANIFEST_VERSION = "looking-glass.manifest.v1"


class Exhibit(Protocol):
    name: str

    def run(self, client: ReadOnlyClient) -> dict[str, Any]: ...


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build(out_dir: Path, exhibits: list[Exhibit], private_key_pem: Path,
          client_factory: Callable[[Path], ReadOnlyClient] | None = None,
          site_dir: Path | None = None) -> dict[str, Any]:
    """Run every exhibit against the public API and write a signed snapshot to `out_dir`.

    Files written: exhibits/<name>.json, requests.jsonl, snapshot.pub.pem, manifest.json,
    manifest.sig. Returns the manifest.

    `site_dir` adds a `page` block: every file of the page itself — markup, styles, script and the
    vendored library — with its sha256. The signature then covers the PAGE as well as the numbers,
    so a stranger can check that the thing rendering these figures is the thing that was published.
    """
    out_dir = Path(out_dir)
    ex_dir = out_dir / "exhibits"
    ex_dir.mkdir(parents=True, exist_ok=True)
    for stale in list(out_dir.glob("*.sig")) + list(ex_dir.glob("*.json")):
        stale.unlink()
    log_path = out_dir / "requests.jsonl"
    client = (client_factory or (lambda lp: ReadOnlyClient(log_path=lp)))(log_path)

    read_ats: list[str] = []
    results: dict[str, dict[str, Any]] = {}
    extra_files: list[Path] = []
    for ex in exhibits:
        payload = ex.run(client)
        payload.setdefault("exhibit", ex.name)
        payload.setdefault("read_at", now_iso())
        read_ats.append(payload["read_at"])
        results[ex.name] = payload
        (ex_dir / f"{ex.name}.json").write_bytes(canonical(payload))
        for rel, data in (getattr(ex, "artifacts", None) or {}).items():
            target = out_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            extra_files.append(target)

    # The endorsement is written once per snapshot key (control/window/make-endorsement.sh) and lives
    # with the page; copy it into the snapshot so it sits at the path the page's instructions name and
    # is covered by the manifest's signature like everything else.
    for carried in ("endorsement.json", "selfrecord.json"):
        if site_dir and (Path(site_dir) / carried).exists():
            target = out_dir / carried
            target.write_bytes((Path(site_dir) / carried).read_bytes())
            extra_files.append(target)

    pub_pem = Path(private_key_pem).with_suffix("").with_suffix(".pub.pem")
    if not pub_pem.exists():
        pub_pem.write_bytes(signing._run(["pkey", "-in", str(private_key_pem), "-pubout"]))
    (out_dir / "snapshot.pub.pem").write_bytes(pub_pem.read_bytes())

    files = []
    for p in sorted(list(ex_dir.glob("*.json")) + [log_path, out_dir / "snapshot.pub.pem"] + extra_files):
        files.append({"path": str(p.relative_to(out_dir)), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    page = None
    if site_dir:
        site_dir = Path(site_dir)
        page = [{"path": str(p.relative_to(site_dir)), "sha256": sha256_file(p), "bytes": p.stat().st_size}
                for p in sorted(site_dir.rglob("*")) if p.is_file() and "__pycache__" not in p.parts]
    manifest = {
        "version": MANIFEST_VERSION,
        "package_version": __version__,
        "built_at": now_iso(),
        "corpus_read_window": {"start": min(read_ats) if read_ats else None,
                               "end": max(read_ats) if read_ats else None},
        "exhibits": sorted(results.keys()),
        "requests": len(client.rows),
        "files": files,
        "signer": {"scheme": "ed25519", "public_key_b64url": signing.public_raw_b64url(pub_pem),
                   "public_key_file": "snapshot.pub.pem",
                   "verify": "looking-glass verify <snapshot dir>  (or: openssl pkeyutl -verify -pubin "
                             "-inkey snapshot.pub.pem -rawin -in manifest.json -sigfile <manifest.sig decoded>)"},
        "reads_and_never_writes": "every network call this build made is in requests.jsonl; all are GET",
    }
    if page is not None:
        manifest["page"] = {
            "files": page,
            "note": ("the page's own bytes, hashed into the same signature as the numbers: markup, styles, "
                     "script, and the one vendored library (Cytoscape, MIT, pinned — see THIRD-PARTY.md). "
                     "Fetch a file from the site, sha256 it, and it must appear here."),
        }
    body = canonical(manifest)
    (out_dir / "manifest.json").write_bytes(body)
    (out_dir / "manifest.sig").write_text(signing.sign(private_key_pem, body), encoding="utf-8")
    return manifest
