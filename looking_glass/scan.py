"""Pre-publish scan (SPEC-004 AC7): the public tree must carry nothing attributable to the operator.

Two layers. STRUCTURAL rules live here and run in the public repo's own tests: no absolute
home paths, no e-mail addresses, no reference to a private vault, no git author trace, no
credentials. PRIVATE patterns (the operator's name, hostnames, machine paths) cannot be
listed in a public file without defeating the purpose, so they are read from a file OUTSIDE
the tree named by the LOOKING_GLASS_FORBIDDEN environment variable, one pattern per line,
and never printed — a hit reports the file and line number only.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

STRUCTURAL = {
    "absolute home path": re.compile(r"(/Users/[A-Za-z0-9_.-]+|/home/[A-Za-z0-9_.-]+|C:\\\\Users\\\\)"),
    "e-mail address": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "private vault reference": re.compile(r"\bvault/"),
    "bearer secret": re.compile(r"1f916_sk_[A-Za-z0-9]+"),
    "private key block": re.compile(r"-----BEGIN (?:ENCRYPTED )?PRIVATE KEY-----"),
    "github token": re.compile(r"\b(ghp|github_pat)_[A-Za-z0-9_]{20,}"),
}
SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", "snapshot", "dist"}
TEXT_SUFFIXES = {".py", ".md", ".toml", ".yml", ".yaml", ".json", ".txt", ".html", ".css", ".js", ".cfg", ".ini", ""}


def _private_patterns() -> list[re.Pattern[str]]:
    src = os.environ.get("LOOKING_GLASS_FORBIDDEN")
    if not src or not Path(src).exists():
        return []
    pats = []
    for line in Path(src).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            pats.append(re.compile(re.escape(line), re.IGNORECASE))
    return pats


def scan(root: Path, allow: set[str] | None = None) -> dict[str, Any]:
    """Return {'ok': bool, 'hits': [{'file','line','rule'}], 'files_scanned': n}."""
    root = Path(root)
    allow = allow or set()
    private = _private_patterns()
    hits: list[dict[str, Any]] = []
    n = 0
    for p in root.rglob("*"):
        if not p.is_file() or any(part in SKIP_DIRS or part.startswith("snapshot") for part in p.relative_to(root).parts):
            continue
        if p.suffix not in TEXT_SUFFIXES or p.name in allow:
            continue
        n += 1
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for rule, rx in STRUCTURAL.items():
                if rx.search(line):
                    hits.append({"file": str(p.relative_to(root)), "line": i, "rule": rule})
            for rx in private:
                if rx.search(line):
                    hits.append({"file": str(p.relative_to(root)), "line": i, "rule": "private pattern"})
    return {"ok": not hits, "hits": hits, "files_scanned": n,
            "private_patterns_loaded": len(private)}
