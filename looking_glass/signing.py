"""Ed25519 signing and verification through the `openssl` command line.

No Python cryptography dependency on purpose: a stranger verifying a snapshot needs only
`openssl` (3.x) and this file's documented commands — the same tool they already trust for
TLS — and nothing from the hosting service. Keys are PEM files; signatures are 64 raw bytes,
carried as unpadded base64url; public keys are also published as the 32 raw bytes in base64url,
the encoding the 1F916 registry uses at GET /api/keys/<handle>.
"""
from __future__ import annotations

import base64
import shutil
import subprocess
import tempfile
from pathlib import Path


def openssl_available() -> bool:
    return shutil.which("openssl") is not None


def _run(args: list[str], input_bytes: bytes | None = None) -> bytes:
    proc = subprocess.run(["openssl", *args], input=input_bytes, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"openssl {args[0]} failed: {proc.stderr.decode(errors='replace').strip()}")
    return proc.stdout


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def unb64url(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def generate_key(private_pem: Path) -> Path:
    """Create an Ed25519 keypair; returns the public PEM path (same stem + .pub.pem)."""
    private_pem = Path(private_pem)
    private_pem.parent.mkdir(parents=True, exist_ok=True)
    _run(["genpkey", "-algorithm", "ed25519", "-out", str(private_pem)])
    private_pem.chmod(0o600)
    pub = private_pem.with_suffix("").with_suffix(".pub.pem")
    pub.write_bytes(_run(["pkey", "-in", str(private_pem), "-pubout"]))
    return pub


def public_raw_b64url(public_pem: Path) -> str:
    """The 32 raw key bytes, base64url unpadded — the registry's encoding."""
    der = _run(["pkey", "-pubin", "-in", str(public_pem), "-pubout", "-outform", "DER"])
    raw = der[-32:]
    if len(raw) != 32:
        raise RuntimeError("public key DER did not end in 32 bytes")
    return b64url(raw)


def sign(private_pem: Path, data: bytes) -> str:
    """Ed25519 signature over `data`, base64url unpadded."""
    with tempfile.TemporaryDirectory() as d:
        msg = Path(d) / "msg"
        msg.write_bytes(data)
        sig = _run(["pkeyutl", "-sign", "-inkey", str(private_pem), "-rawin", "-in", str(msg)])
    if len(sig) != 64:
        raise RuntimeError(f"signature was {len(sig)} bytes, expected 64")
    return b64url(sig)


def verify(public_pem: Path, data: bytes, signature_b64url: str) -> bool:
    """True iff `signature_b64url` is a valid Ed25519 signature over `data` under the key."""
    with tempfile.TemporaryDirectory() as d:
        msg, sigf = Path(d) / "msg", Path(d) / "sig"
        msg.write_bytes(data)
        sigf.write_bytes(unb64url(signature_b64url))
        proc = subprocess.run(
            ["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(public_pem), "-rawin",
             "-in", str(msg), "-sigfile", str(sigf)], capture_output=True, check=False)
    return proc.returncode == 0 and b"Verified Successfully" in proc.stdout


def public_pem_from_raw(raw_b64url: str) -> bytes:
    """Wrap 32 raw Ed25519 public-key bytes (registry encoding) as a PEM openssl accepts."""
    raw = unb64url(raw_b64url)
    if len(raw) != 32:
        raise ValueError("raw Ed25519 public key must be 32 bytes")
    prefix = bytes.fromhex("302a300506032b6570032100")  # SubjectPublicKeyInfo header for Ed25519
    der = prefix + raw
    body = base64.encodebytes(der).decode().replace("\n", "")
    lines = "\n".join(body[i:i + 64] for i in range(0, len(body), 64))
    return f"-----BEGIN PUBLIC KEY-----\n{lines}\n-----END PUBLIC KEY-----\n".encode()
