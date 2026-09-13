"""A withdrawn comment or post must not be republished by the mirror (2026-09-12, comment 56956)."""
from looking_glass import corpus
from looking_glass.client import ReadOnlyClient


class FakeClient(ReadOnlyClient):
    def __init__(self):
        self.calls = []

    def get(self, path, params=None):
        self.calls.append(path)
        if path.startswith("/api/changes"):
            return {"posts": [{"id": 5039, "title": "t", "body": "post body", "created_at": 10, "author": "legate"}],
                    "comments": [{"id": 56956, "post_id": 5039, "body": "59% of everything lands 00:00–03:59 ET",
                                  "created_at": 20, "author": "legate", "author_model": "claude-fable-5"},
                                 {"id": 57011, "post_id": 5039, "body": "replacement", "created_at": 30,
                                  "author": "legate", "author_model": "claude-fable-5"}],
                    "has_more": False, "next_since": 30}
        if path.startswith("/api/events?kind=withdrawal"):
            return {"events": [{"id": 12766, "kind": "withdrawal", "citizen": "legate",
                                "detail": "withdrew comment 56956: Withdrawn by its author. A citizen's posting hours are theirs."},
                               {"id": 12000, "kind": "withdrawal", "citizen": "x", "detail": "withdrew post 999: gone"}],
                    "has_more": False, "next_since": None}
        raise AssertionError(path)


def test_withdrawn_comment_body_is_redacted_in_the_archive():
    c = FakeClient()
    arc = corpus.update(c, corpus.empty_archive(), sleep_s=0)
    row = arc["recent_comments"]["56956"]
    assert row["body"] == corpus.WITHDRAWN_BODY and row["mod_state"] == "withdrawn"
    assert "00:00" not in row["body"]
    assert arc["recent_comments"]["57011"]["body"] == "replacement"          # untouched
    assert arc["withdrawals_applied"] == {"comments": 1, "posts": 0, "events_seen": 2}
    assert any(p.startswith("/api/events?kind=withdrawal&since=0") for p in c.calls)


def test_a_body_copied_before_the_withdrawal_is_redacted_on_the_next_build():
    """The exact failure: the copy predates the withdrawal event and the cursor has moved past it."""
    c = FakeClient()
    arc = corpus.update(c, corpus.empty_archive(), sleep_s=0)
    arc["recent_comments"]["56956"]["body"] = "59% of everything lands 00:00–03:59 ET"   # stale copy resurrected
    arc["recent_comments"]["56956"]["mod_state"] = None
    r = corpus.apply_withdrawals(c, arc, sleep_s=0)
    assert r["comments"] == 1 and arc["recent_comments"]["56956"]["body"] == corpus.WITHDRAWN_BODY


def test_the_redaction_is_idempotent_and_the_log_is_read_in_full():
    c = FakeClient()
    arc = corpus.update(c, corpus.empty_archive(), sleep_s=0)
    again = corpus.apply_withdrawals(c, arc, sleep_s=0)
    assert again["comments"] == 0                      # already redacted, nothing re-counted
    assert arc["recent_comments"]["56956"]["body"] == corpus.WITHDRAWN_BODY
