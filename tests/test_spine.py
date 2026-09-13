"""SPEC-004 spine: AC1 (GET only, logged), AC2 (manifest + signature), AC3 (stranger verify), AC7 (scan)."""
import json
from pathlib import Path

import pytest

from looking_glass import scan, signing, snapshot, verify
from looking_glass.client import ReadOnlyClient, WriteAttempt

pytestmark = pytest.mark.skipif(not signing.openssl_available(), reason="openssl required")


class FakeClient(ReadOnlyClient):
    """Same logging path as the real client; the network is replaced by a table."""
    def __init__(self, log_path, table):
        super().__init__(log_path=log_path)
        self.table = table

    def get(self, path, params=None):
        body = json.dumps(self.table[path]).encode()
        self._log(self.origin + path, 200, body, 0.0)
        return json.loads(body)


class Ex:
    name = "fake"

    def run(self, client):
        d = client.get("/api/pulse")
        return {"read_at": "2026-09-10T18:00:00Z", "sentence": "x", "data": d}


def test_client_has_one_verb_and_refuses_absolute_urls(tmp_path):
    c = ReadOnlyClient(log_path=tmp_path / "log.jsonl")
    assert not any(hasattr(c, m) for m in ("post", "put", "delete", "patch"))
    with pytest.raises(WriteAttempt):
        c.get("https://elsewhere.example/api/pulse")


def test_signing_roundtrip_and_registry_encoding(tmp_path):
    pub = signing.generate_key(tmp_path / "k.pem")
    sig = signing.sign(tmp_path / "k.pem", b"hello")
    assert signing.verify(pub, b"hello", sig)
    assert not signing.verify(pub, b"hellO", sig)
    raw = signing.public_raw_b64url(pub)
    assert len(signing.unb64url(raw)) == 32
    # the registry's raw encoding round-trips to a PEM openssl accepts
    pem2 = tmp_path / "k2.pub.pem"
    pem2.write_bytes(signing.public_pem_from_raw(raw))
    assert signing.verify(pem2, b"hello", sig)


def test_build_writes_signed_manifest_and_verify_passes(tmp_path):
    signing.generate_key(tmp_path / "snap.pem")
    out = tmp_path / "snapshot"
    table = {"/api/pulse": {"board": {"citizens": 3}}}
    m = snapshot.build(out, [Ex()], tmp_path / "snap.pem",
                       client_factory=lambda lp: FakeClient(lp, table))
    assert (out / "manifest.json").exists() and (out / "manifest.sig").exists()
    assert m["requests"] == 1 and m["exhibits"] == ["fake"]
    assert m["corpus_read_window"] == {"start": "2026-09-10T18:00:00Z", "end": "2026-09-10T18:00:00Z"}
    r = verify.verify_snapshot(out)
    assert r["ok"] and r["files_ok"] and r["signature_ok"] and r["requests_all_get"]
    log = [json.loads(l) for l in (out / "requests.jsonl").read_text().splitlines()]
    assert log and all(row["method"] == "GET" for row in log)


def test_verify_refutes_a_tampered_exhibit_and_a_tampered_manifest(tmp_path):
    signing.generate_key(tmp_path / "snap.pem")
    out = tmp_path / "snapshot"
    snapshot.build(out, [Ex()], tmp_path / "snap.pem",
                   client_factory=lambda lp: FakeClient(lp, {"/api/pulse": {"n": 1}}))
    ex = out / "exhibits" / "fake.json"
    ex.write_bytes(ex.read_bytes().replace(b'"n":1', b'"n":2'))
    r = verify.verify_snapshot(out)
    assert not r["ok"] and not r["files_ok"] and r["signature_ok"]
    # now the manifest itself
    mf = out / "manifest.json"
    mf.write_bytes(mf.read_bytes().replace(b"looking-glass.manifest.v1", b"looking-glass.manifest.v9"))
    r2 = verify.verify_snapshot(out)
    assert not r2["signature_ok"]


def test_verify_refuses_a_foreign_key(tmp_path):
    signing.generate_key(tmp_path / "snap.pem")
    other = signing.generate_key(tmp_path / "other.pem")
    out = tmp_path / "snapshot"
    snapshot.build(out, [Ex()], tmp_path / "snap.pem",
                   client_factory=lambda lp: FakeClient(lp, {"/api/pulse": {"n": 1}}))
    r = verify.verify_snapshot(out, public_pem=other)
    assert not r["ok"] and not r["signature_ok"] and not r["key_matches_manifest"]


def test_endorsement_verifies_against_registry_encoded_citizen_key(tmp_path):
    cit_pub = signing.generate_key(tmp_path / "citizen.pem")
    snap_pub = signing.generate_key(tmp_path / "snap.pem")
    snap_raw = signing.public_raw_b64url(snap_pub)
    msg = verify.endorsement_message("legate", snap_raw, "2026-09-10")
    e = {"version": verify.ENDORSEMENT_VERSION, "handle": "legate", "snapshot_public_key_b64url": snap_raw,
         "day": "2026-09-10", "signature_b64url": signing.sign(tmp_path / "citizen.pem", msg.encode())}
    assert verify.verify_endorsement(e, signing.public_raw_b64url(cit_pub))["ok"]
    e["day"] = "2026-09-11"
    assert not verify.verify_endorsement(e, signing.public_raw_b64url(cit_pub))["ok"]


def test_scan_flags_home_paths_emails_vault_and_private_patterns(tmp_path, monkeypatch):
    (tmp_path / "ok.py").write_text("x = 1\n")
    (tmp_path / "bad.md").write_text("see " + "/Us" + "ers/someone/dev and mail me at a" + "@" + "b.io and va" + "ult/ledgers\n")
    forb = tmp_path.parent / "forbidden.txt"
    forb.write_text("SecretHostname\n")
    (tmp_path / "host.txt").write_text("built on secrethostname\n")
    monkeypatch.setenv("LOOKING_GLASS_FORBIDDEN", str(forb))
    r = scan.scan(tmp_path)
    rules = {h["rule"] for h in r["hits"]}
    assert not r["ok"]
    assert {"absolute home path", "e-mail address", "private vault reference", "private pattern"} <= rules
    assert r["private_patterns_loaded"] == 1
    # a hit never echoes the matched text
    assert all(set(h) == {"file", "line", "rule"} for h in r["hits"])


# --- rate limiting: added 2026-09-10 after a 429 killed the hourly build mid-page ---

def test_429_is_retried_with_the_registrys_own_retry_after():
    import urllib.error
    from looking_glass import client as C

    calls, slept = [], []

    class Resp:
        status = 200
        def read(self): return b'{"ok":true}'
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=None):
        calls.append(req.full_url)
        if len(calls) == 1:
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests",
                                         {"Retry-After": "3"}, None)
        return Resp()

    orig_open, orig_sleep = C.urllib.request.urlopen, C.time.sleep
    C.urllib.request.urlopen = fake_urlopen
    C.time.sleep = lambda s: slept.append(s)
    try:
        c = C.ReadOnlyClient()
        assert c.get("/api/events") == {"ok": True}
    finally:
        C.urllib.request.urlopen, C.time.sleep = orig_open, orig_sleep

    assert len(calls) == 2, "the 429 must be retried, not raised"
    assert 3 in slept, "the registry said Retry-After: 3 and that is what must be waited"
    # the refusal is in the log, not swallowed: a hidden 429 is a lie about what was asked for
    assert [r["status"] for r in c.rows] == [429, 200]
    assert c.rows[0]["retrying"] is True


def test_a_persistent_429_fails_loudly_rather_than_retrying_forever():
    import urllib.error
    import pytest
    from looking_glass import client as C

    def always_429(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, None)

    orig_open, orig_sleep = C.urllib.request.urlopen, C.time.sleep
    C.urllib.request.urlopen = always_429
    C.time.sleep = lambda s: None
    try:
        c = C.ReadOnlyClient()
        with pytest.raises(C.RateLimited) as e:
            c.get("/api/events")
    finally:
        C.urllib.request.urlopen, C.time.sleep = orig_open, orig_sleep

    assert "more than its share" in str(e.value), "the message must name the cause, not the symptom"
    assert len(c.rows) == C.MAX_ATTEMPTS, "every attempt, including the refusals, is logged"


def test_a_404_is_not_retried():
    import urllib.error
    import pytest
    from looking_glass import client as C

    calls = []

    def gone(req, timeout=None):
        calls.append(1)
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

    orig_open, orig_sleep = C.urllib.request.urlopen, C.time.sleep
    C.urllib.request.urlopen = gone
    C.time.sleep = lambda s: None
    try:
        c = C.ReadOnlyClient()
        with pytest.raises(urllib.error.HTTPError):
            c.get("/api/post/999999")
    finally:
        C.urllib.request.urlopen, C.time.sleep = orig_open, orig_sleep
    assert len(calls) == 1, "a missing post is an answer, not a reason to ask again"
