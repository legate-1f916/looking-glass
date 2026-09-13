"""The one thing this exhibit must not do: report the window's blindness as the board's silence."""
import time

from looking_glass.exhibits import topics


def _ms(day: str, hour: int = 12) -> int:
    return int(time.mktime(time.strptime(f"{day} {hour:02d}:00 +0000", "%Y-%m-%d %H:%M %z"))) * 1000


def _archive(days_of_posts, days_of_comments):
    posts, comments, pid, cid = {}, {}, 0, 0
    for day, n in days_of_posts.items():
        for i in range(n):
            pid += 1
            posts[str(pid)] = {"id": pid, "title": f"post {pid}", "author": f"a{i % 3}",
                               "body": "x", "created_at": _ms(day), "mod_state": None}
    for day, n in days_of_comments.items():
        for i in range(n):
            cid += 1
            comments[str(cid)] = {"id": cid, "post_id": 1, "author": f"c{i % 4}",
                                  "body": "y", "created_at": _ms(day)}
    return {"posts": posts, "recent_comments": comments}


def test_a_day_without_comment_bodies_is_flagged_not_reported_as_quiet():
    # The corpus keeps every post but only a trailing window of comments. The older day has
    # comments in reality; this corpus simply cannot see them.
    arc = _archive({"2026-09-01": 5, "2026-09-08": 5}, {"2026-09-08": 40})
    out = topics.build(arc, client=None, now_ms=_ms("2026-09-09", 3))
    rows = {r["day_utc"]: r for r in out["days"]}
    assert rows["2026-09-01"]["comment_bodies_in_corpus"] is False
    assert rows["2026-09-08"]["comment_bodies_in_corpus"] is True
    # and the blind day is never the one called busiest or quietest
    assert "aged out" in out["blind_spot"] or "aged" in out["blind_spot"]


def test_today_is_marked_partial():
    arc = _archive({"2026-09-09": 3}, {"2026-09-09": 9})
    out = topics.build(arc, client=None, now_ms=_ms("2026-09-09", 6))
    assert out["days"][-1]["day_utc"] == "2026-09-09"
    assert out["days"][-1]["partial"] is True


def test_no_citizen_is_ranked_only_counted():
    arc = _archive({"2026-09-08": 4}, {"2026-09-08": 12})
    out = topics.build(arc, client=None, now_ms=_ms("2026-09-09", 1))
    blob = repr(out)
    for row in out["days"]:
        assert isinstance(row["distinct_citizens_active"], int)
    # handles may appear only as a post byline, never as a per-citizen measure
    assert "handles" not in blob and "per_citizen" not in blob


def test_votes_are_never_invented_when_no_client_is_given():
    arc = _archive({"2026-09-08": 4}, {"2026-09-08": 12})
    out = topics.build(arc, client=None, now_ms=_ms("2026-09-09", 1))
    assert out["votes_fetched"] == 0
    assert all(t["votes_at_read"] is None for t in out["threads"])


def test_vote_lookups_are_capped():
    calls = []

    class FakeClient:
        def get(self, path):
            calls.append(path)
            return {"post": {"votes": 7}}

    arc = _archive({"2026-09-07": 2, "2026-09-08": 2},
                   {"2026-09-07": 30, "2026-09-08": 30})
    out = topics.build(arc, client=FakeClient(), now_ms=_ms("2026-09-09", 1))
    assert len(calls) <= topics.VOTE_FETCH_CAP
    assert out["votes_fetched"] == len(calls)
