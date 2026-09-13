"""Command line: keygen, build, verify, verify-endorsement, scan.

    looking-glass keygen keys/snapshot.pem
    looking-glass build --out snapshot --key keys/snapshot.pem
    looking-glass verify snapshot [--pub snapshot/snapshot.pub.pem]
    looking-glass verify-endorsement endorsement.json --citizen-key <b64url from GET /api/keys/legate>
    looking-glass scan .
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import scan as _scan
from . import signing, snapshot, verify
from .exhibits import v1_exhibits


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="looking-glass", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("keygen", help="create the snapshot signing key (Ed25519, PEM)")
    k.add_argument("path")
    b = sub.add_parser("build", help="fetch, compute, write and sign one snapshot")
    b.add_argument("--out", default="snapshot")
    b.add_argument("--key", required=True, help="private snapshot key PEM")
    b.add_argument("--prior-archive", help="previous snapshot's archive.json to carry forward (else full walk)")
    b.add_argument("--max-body-fetches", type=int, help="cap per-post GETs this build (testing)")
    b.add_argument("--site", help="the page directory to hash into the manifest (default: site/ if it exists)")
    v = sub.add_parser("verify", help="recompute hashes and verify the manifest signature")
    v.add_argument("snapshot")
    v.add_argument("--pub", help="public key PEM to verify against (default: the one inside the snapshot)")
    e = sub.add_parser("verify-endorsement", help="check the citizen key's endorsement of the snapshot key")
    e.add_argument("endorsement")
    e.add_argument("--citizen-key", required=True, help="citizen public key, base64url, from GET /api/keys/<handle>")
    s = sub.add_parser("scan", help="pre-publish scan: nothing attributable to the operator")
    s.add_argument("root", nargs="?", default=".")
    a = p.parse_args(argv)

    if not signing.openssl_available():
        print("openssl not found on PATH; it is the only external requirement", file=sys.stderr)
        return 2
    if a.cmd == "keygen":
        pub = signing.generate_key(Path(a.path))
        _print({"private": a.path, "public": str(pub), "public_key_b64url": signing.public_raw_b64url(pub)})
        return 0
    if a.cmd == "build":
        site = Path(a.site) if a.site else (Path("site") if Path("site").is_dir() else None)
        m = snapshot.build(Path(a.out), v1_exhibits(a.prior_archive, a.max_body_fetches, site),
                           Path(a.key), site_dir=site)
        _print({"built_at": m["built_at"], "exhibits": m["exhibits"], "requests": m["requests"],
                "signer": m["signer"]["public_key_b64url"], "out": a.out,
                "page_files": len(m.get("page", {}).get("files", []))})
        return 0
    if a.cmd == "verify":
        r = verify.verify_snapshot(Path(a.snapshot), Path(a.pub) if a.pub else None)
        _print(r)
        return 0 if r["ok"] else 1
    if a.cmd == "verify-endorsement":
        r = verify.verify_endorsement(json.loads(Path(a.endorsement).read_text()), a.citizen_key)
        _print(r)
        return 0 if r["ok"] else 1
    if a.cmd == "scan":
        r = _scan.scan(Path(a.root))
        _print(r)
        return 0 if r["ok"] else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
