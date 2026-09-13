"""The only door to the network: HTTP GET against the public 1F916 API, every call logged.

SPEC-004 AC1 — "It reads and never writes." This class has one verb. It never sends an
Authorization header, never a body, never a cookie, and it refuses any origin but the one it
was built for. Every request appends a row to the request log that ships inside the snapshot,
so a stranger can read what the build fetched rather than trust a description of it.

BEING A GOOD GUEST. 1F916 is a shared public API and this window is an uninvited reader of it.
Until 2026-09-10 this client asked as fast as the socket allowed, which stayed under the
registry's limit only by luck; adding twelve requests to the hourly build was enough to earn a
429 in the middle of paging the identity log, and the build died. So there is now a floor
between requests and a backoff that honours `Retry-After` when the registry sends one.

Every attempt is logged, the refusals included. The request log is this window's proof that it
reads and never writes, and a log that quietly hid the requests that were turned away would be
a worse kind of dishonest than the number it was protecting.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ORIGIN = "https://1f916.ai"
USER_AGENT = "looking-glass/0.1 (reads and never writes; https://1f916.ai/api/listings/23)"

MIN_INTERVAL_S = 0.75       # a floor between requests. The 429 of 2026-09-10 arrived after
                            # five requests inside one second, so the limit the registry
                            # enforces is a BURST limit; spacing is the fix, not retrying.
RETRY_STATUSES = (429, 500, 502, 503, 504)
MAX_ATTEMPTS = 5
BACKOFF_S = (2, 5, 12, 30)  # used when the registry does not say Retry-After
MAX_WAIT_S = 60             # never sit on a single request longer than this


class WriteAttempt(RuntimeError):
    """Raised if anything asks this client to do something other than GET the origin."""


class RateLimited(RuntimeError):
    """The registry kept saying no. Raised only after the backoff is exhausted, so that a build
    which fails for this reason says so plainly instead of looking like a broken chain."""


def _retry_after_seconds(headers) -> float | None:
    raw = headers.get("Retry-After") if headers else None
    if not raw:
        return None
    try:
        return min(float(raw), MAX_WAIT_S)
    except ValueError:
        pass
    try:
        from email.utils import parsedate_to_datetime
        import datetime
        when = parsedate_to_datetime(raw)
        if when.tzinfo is None:
            when = when.replace(tzinfo=datetime.timezone.utc)
        return max(0.0, min((when - datetime.datetime.now(datetime.timezone.utc)).total_seconds(), MAX_WAIT_S))
    except Exception:  # noqa: BLE001 — an unparseable header falls back to the fixed backoff
        return None


class ReadOnlyClient:
    def __init__(self, log_path: Path | None = None, origin: str = ORIGIN, timeout: int = 30):
        self.origin = origin.rstrip("/")
        self.timeout = timeout
        self.log_path = Path(log_path) if log_path else None
        self.rows: list[dict[str, Any]] = []
        self._last_request_at = 0.0
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_path.write_text("", encoding="utf-8")

    # The one verb. There is deliberately no post/put/delete and no header hook.
    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if "://" in path:
            raise WriteAttempt(f"absolute URLs are refused; pass a path under {self.origin}")
        if not path.startswith("/"):
            path = "/" + path
        url = self.origin + path
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, method="GET", headers={
            "Accept": "application/json", "User-Agent": USER_AGENT})

        for attempt in range(1, MAX_ATTEMPTS + 1):
            self._space_out()
            t0 = time.time()
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310 - fixed origin
                    status, body = resp.status, resp.read()
                self._log(url, status, body, t0, attempt)
                return json.loads(body.decode("utf-8"))
            except urllib.error.HTTPError as e:
                status, body = e.code, e.read()
                self._log(url, status, body, t0, attempt, retrying=status in RETRY_STATUSES
                          and attempt < MAX_ATTEMPTS)
                if status not in RETRY_STATUSES or attempt == MAX_ATTEMPTS:
                    if status == 429:
                        raise RateLimited(
                            f"the registry answered 429 to {url} on {attempt} attempts. This build "
                            f"asks for more than its share; reduce what it fetches rather than "
                            f"retrying harder.") from e
                    raise
                wait = _retry_after_seconds(e.headers)
                if wait is None:
                    wait = BACKOFF_S[min(attempt - 1, len(BACKOFF_S) - 1)]
                time.sleep(wait)
        raise RateLimited(f"gave up on {url}")  # unreachable; kept so the function has one exit shape

    def _space_out(self) -> None:
        """A floor between requests. Politeness toward a shared API, not a performance knob."""
        gap = time.time() - self._last_request_at
        if gap < MIN_INTERVAL_S:
            time.sleep(MIN_INTERVAL_S - gap)
        self._last_request_at = time.time()

    def _log(self, url: str, status: int, body: bytes, t0: float,
             attempt: int = 1, retrying: bool = False) -> None:
        row = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)),
            "method": "GET",
            "url": url,
            "status": status,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
            "ms": int((time.time() - t0) * 1000),
        }
        # Only present when something went wrong, so an ordinary log stays readable — but always
        # present when it did, because a hidden refusal is a lie about what this build asked for.
        if attempt > 1:
            row["attempt"] = attempt
        if retrying:
            row["retrying"] = True
        self.rows.append(row)
        if self.log_path:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, sort_keys=True) + "\n")
