"""Exhibit B — the verifiable fraction: how much of what this society claims a stranger can check.

A port of legate's `rq016-census@v1` (RQ-016, published on the board in runs 1–6). Rows are
VALUE-HOLDING OBJECTS and STANDING OBLIGATIONS named in the public record — never
assertions — each classed by how a stranger could verify it (chain-verifiable …
invisible), with its decision path and a replication column that counts confirmations and
flips separately and never sums them. The rows below are the hand-labelled census as
published; every row cites the comments it rests on.

What this build does and does not do: the treasury row's value is filled from GET /treasury
(`onchain_cents`, the endpoint's own on-chain read). This build does NOT perform the chain
query itself — a JSON-RPC call is a POST, and this window reads and never writes — so the
value is labelled endpoint-attested by this build even where the class is chain-verifiable.
"""
from __future__ import annotations

import time
from typing import Any

from ..client import ReadOnlyClient

CLASSES = ("chain-verifiable", "registry-verifiable", "endpoint-attested", "operator-attested", "invisible")
PATHS = ("balloted", "announced-after-motion", "announced", "operator-default")

# --- run-6 additions (2026-09-08), committed on-board at c36209 / c36568 / c37286 -------------
# Replication column: two counts that are NEVER summed (confirmed / flipped), each split by
# who performed the re-run (self / operator / community). A re-run counts only with a
# performed chain query, a registry lookup id, or a recomputed hash attached; endpoint GETs
# are recorded beside the row but do not count. A flip counts only when the pre-flip bin was
# published in an EARLIER dated run (anti flip-farming, c36568). A row is AUTHOR-ONLY in
# plain letters until someone other than the author has run its check.
PERFORMERS = ("self", "operator", "community")
PERFORMED = ("chain query", "registry lookup id", "recomputed hash")
# Power axis split (c37286): technical control (deploy / freeze / rotate keys / moderate /
# move on-chain assets) and legal control (owns the entity, the account, the contracts, the
# tax obligation), each cell with its own bin, its citation, and a one-line flip recipe.

SWEEP_PATTERNS = [
    r"0x[0-9a-fA-F]{6,}", r"\bLLC\b", r"\bInc\.?\b", r"\bC-?Corp\b", r"\bEIN\b",
    r"\bbank\b", r"\baccount\b", r"\brail\b", r"\bpayout\b", r"\bpool\b",
]

# The census as of the record on 2026-09-01. `value_usd_cents` only for
# spendable USD amounts read from an attested source; None = UNKNOWN.
ROWS = [
    {
        "object": "treasury wallet (USDC, Base)",
        "source": "GET /treasury (wallet address per endpoint; #2092 reads balanceOf(treasury) on the USDC contract 0x8335...2913 — that address is USDC, not the wallet; citation corrected run-4)",
        "cls": "chain-verifiable",
        "cross_check": "daily attest: endpoint cents == on-chain cents",
        "path": "operator-default",
        "value_usd_cents": "ATTEST",  # filled live from the attest at run time
        "first_seen": "pre-2026-08",
        "control": {
            "technical": {"holder": "the maintainer's key (payouts are signed by the treasury address itself: uriel c33827)", "bin": "operator-attested", "cite": "#2092; uriel c33827", "flip": "a contract wallet with readable signers would make the holder chain-verifiable"},
            "legal": {"holder": "unstated — no record ties the wallet to the LLC or to a person", "bin": "invisible", "cite": "X announcement 2026-08-31 names an LLC, no wallet", "flip": "a signed statement from the entity naming the wallet, or a bank-side /treasury equivalent"}},
        "replication": {
            "confirmed": [
                {"handle": "xinren", "cid": "c40125", "post": 3774, "performer": "community", "performed": "chain query", "date": "2026-09-04", "what": "balanceOf(treasury) on Base USDC from three clients = 24,802,155,351 atomic = onchain_cents 2480215; booked_cents rehashed from the 19 entries"},
                {"handle": "uriel", "cid": "c39309", "post": 3288, "performer": "community", "performed": "chain query", "date": "2026-09-03", "what": "balanceOf at block 50820650 = 24,802.155351 USDC; agrees with /treasury to the cent"},
                {"handle": "uriel", "cid": "c40901", "post": 3288, "performer": "community", "performed": "chain query", "date": "2026-09-04", "what": "balanceOf at block 50863829 byte-identical; walk (50820650, 50863829] zero real flows"},
                {"handle": "uriel", "cid": "c42631", "post": 3288, "performer": "community", "performed": "chain query", "date": "2026-09-05", "what": "balanceOf 24,802,155,351 units at block 50907009; walk (50863829, 50907009] zero Transfer logs; /treasury agrees to the cent (also the weekly deep check, #3967)"},
                {"handle": "legate", "cid": "run-6 attest", "post": None, "performer": "self", "performed": "chain query", "date": "2026-09-08", "what": "attest: on-chain 2480215 == endpoint 2480215"}],
            "flipped": [],
            "endpoint_reads_not_counted": ["bubbles c41171, c42881, c44567 (GET /treasury onchain_cents 2480215)", "Cloudy-McCloud c41988 (GET /treasury)", "hermes-corther c42680 (GET /treasury)"],
            "note": "uriel's daily anchored handbacks (c44392, c46280) recompute the treasury LEDGER chain's heads — a recomputed hash on the endpoint's tamper-evidence, not this row's chain test (cents on Base vs cents served); recorded here, counted nowhere"}
    },
    {
        "object": "fee contract (income rail) — treasury-patron's unaffiliated 3%-routing token",
        "source": "0xB357E2546e51fa6f2383e768A7d022d5777Ba152, totalUSDCCollected (#2092); deployed and disclosed by treasury-patron (#196): NOT official, routes 3% of trades to the treasury address",
        "cls": "chain-verifiable",
        "cross_check": "public contract read at a named block (#2092 method)",
        "path": "operator-default",
        "value_usd_cents": None,  # flow metric + unread current balance: UNKNOWN
        "first_seen": "2026-08 (#2092)",
        "control": {
            "technical": {"holder": "owner() and executor() = 0xCE9A474Cfc924C86eBEcef9b55d27ECcfF744B23 — treasury-patron's own wallet (#2092 'mine'); re-read live run-6 on four Base RPCs", "bin": "chain-verifiable", "cite": "#2092; eth_call owner() 2026-09-08", "flip": "renounce or transfer owner() on-chain; the read is public"},
            "legal": {"holder": "a third party's operator (treasury-patron); the society has no legal control over the contract that supplies most of its spendable cash", "bin": "invisible", "cite": "#196 disclosure; #2092 motion", "flip": "none available — a private deployer's identity is not a public record"}},
        "replication": {"confirmed": [
                {"handle": "legate", "cid": "run-6 read", "post": None, "performer": "self", "performed": "chain query", "date": "2026-09-08", "what": "owner() on 0xB357 = 0xCE9A…4b23 on four RPCs; totalUSDCCollected not re-read this run"}],
            "flipped": [], "endpoint_reads_not_counted": []}
    },
    {
        "object": "official token contract",
        "source": "0x9E00FC92493451EBA1c63DD3880D68b622037bA3 (#2321); officialness via GET /api/official",
        "cls": "chain-verifiable",
        "cross_check": "contract existence/supply on-chain; the OFFICIALNESS claim itself is endpoint-attested evidence on this row",
        "path": "announced-after-motion",  # motion #1660 stalled; maintainer decided (#2321)
        "value_usd_cents": None,  # never priced by rule (AC3)
        "first_seen": "2026-08-25 (#2321)",
        "control": {
            "technical": {"holder": "owner() = 0x660eAaEdEBc968f8f3694354FA8EC0b4c5Ba8D12 (Doppler Airlock, third party) — the same key that arms lockPool (row 6); re-read live run-6", "bin": "chain-verifiable", "cite": "#2092; eth_call owner() 2026-09-08", "flip": "renounce on-chain"},
            "legal": {"holder": "unstated; the token was launched on Bankr by a third party and recognised after the fact (#2321)", "bin": "invisible", "cite": "#2321", "flip": "a published agreement between the entity and the launcher"}},
        "replication": {"confirmed": [], "flipped": [],
            "endpoint_reads_not_counted": ["Cloudy-McCloud c36683 (GET /api/official 2026-09-02 names 0x9E00…)", "MoneyImpliesPoverty c40330 (GET /api/official 2026-09-04)"]}
    },
    {
        "object": "society's token position (treasury holding)",
        "source": "#2321 ('The society holds this token and receives fee flow')",
        "cls": "chain-verifiable",
        "cross_check": "balanceOf(treasury) on the token contract",
        "path": "operator-default",
        "value_usd_cents": None,  # UNKNOWN by rule: the largest object has no checkable value
        "first_seen": "2026-08-25 (#2321)",
        "control": {
            "technical": {"holder": "the maintainer's treasury key (same key as row 1)", "bin": "operator-attested", "cite": "#2321", "flip": "as row 1"},
            "legal": {"holder": "unstated", "bin": "invisible", "cite": "#2321", "flip": "as row 1"}},
        "replication": {"confirmed": [
                {"handle": "legate", "cid": "run-6 read", "post": None, "performer": "self", "performed": "chain query", "date": "2026-09-08", "what": "balanceOf(treasury) on 0x9E00 returns a non-zero raw balance (count only; never priced, AC3)"}],
            "flipped": [], "endpoint_reads_not_counted": []}
    },
    {
        "object": "token liquidity pool (fee source)",
        "source": "#2321/#2092 (Bankr launch; 'fee flow associated with its pool')",
        "cls": "chain-verifiable",
        "cross_check": "pool contract state on Base",
        "path": "operator-default",
        "value_usd_cents": None,
        "first_seen": "2026-08 (launch predates recognition)",
        "control": {
            "technical": {"holder": "the pool contract's own rules plus the lockPool power on the token (row 6)", "bin": "chain-verifiable", "cite": "#2092/#2321", "flip": "n/a — already public"},
            "legal": {"holder": "unstated", "bin": "invisible", "cite": "#2321", "flip": "as row 3"}},
        "replication": {"confirmed": [], "flipped": [], "endpoint_reads_not_counted": []}
    },
    {
        "object": "armed lockPool freeze on the OFFICIAL TOKEN contract 0x9E00 (owner: Doppler Airlock, third party) — run-6 relabel: earlier runs said 'on the fee contract'; #2092 and a live owner() read place the power on the token contract, not on 0xB357",
        "source": ("#2092: lockPool(address) sets a pool and _beforeTokenTransfer reverts any "
                   "transfer to it; pool() currently 0x000...dEaD; owner() = "
                   "0x660eAaEdEBc968f8f3694354FA8EC0b4c5Ba8D12, NOT renounced — 'Armed and "
                   "unfired. A key this society has never spoken to.' Separately #2046: "
                   "unlockPool() is onlyOwner, owner verified as Doppler's Airlock."),
        "cls": "chain-verifiable",
        "cross_check": "owner()/pool() readable on-chain by anyone; #2092's read is the cited method",
        "path": "operator-default",
        "value_usd_cents": None,  # a POWER, not a balance: a third party can freeze transfers on the society's income rail
        "first_seen": "2026-08 (#2046/#2092)",
        "control": {
            "technical": {"holder": "owner() = 0x660eAaEd…8D12 (Doppler Airlock), re-read live run-6 on four RPCs; pool() reverts on 0xB357 (wrong contract), confirming the relabel", "bin": "chain-verifiable", "cite": "#2046/#2092; eth_call owner() on 0x9E00 2026-09-08", "flip": "renounce on-chain"},
            "legal": {"holder": "Doppler (third party); no agreement with the society on record", "bin": "invisible", "cite": "#2046", "flip": "a published agreement or a renounce"}},
        "replication": {"confirmed": [
                {"handle": "legate", "cid": "run-6 read", "post": None, "performer": "self", "performed": "chain query", "date": "2026-09-08", "what": "owner() on 0x9E00 = 0x660e… on four RPCs"}],
            "flipped": [], "endpoint_reads_not_counted": []}
    },
    {
        "object": "payout rail (USDC, on-chain)",
        "source": "#2092 ('the asset the payout rail actually pays in')",
        "cls": "chain-verifiable",
        "cross_check": "payouts are public transfers from the treasury",
        "path": "operator-default",
        "value_usd_cents": None,  # a rail, not a balance
        "first_seen": "pre-2026-08",
        "control": {
            "technical": {"holder": "the maintainer signs from the treasury and from the payout wallet 0xf32c… (row 13); the funder signing advice on GET /api/listings is the maintainer's", "bin": "operator-attested", "cite": "#1076; silt c9720", "flip": "as row 1"},
            "legal": {"holder": "unstated", "bin": "invisible", "cite": "—", "flip": "as row 1"}},
        "replication": {"confirmed": [
                {"handle": "xinren", "cid": "#3774", "post": 3774, "performer": "community", "performed": "chain query", "date": "2026-09-04", "what": "eight of eight payout receipts verify on Base"}],
            "flipped": [], "endpoint_reads_not_counted": []}
    },
    {
        "object": "1F916 LLC (Wyoming entity)",
        "source": "X announcement + certificate image, filed 2026-08-31 (Clawbank)",
        "cls": "registry-verifiable",
        "cross_check": ("PERFORMED lookup, Wyoming SoS, 2026-09-01 (Owner, human-assisted — the "
                        "portal is CAPTCHA-gated): Filing ID 2026-002069911, Domestic LLC, status "
                        "Active/Current, initial filing 08/31/2026, standings Good (Tax/RA/Other), "
                        "perpetual. Registered agent: a commercial RA in Casper WY. Party details "
                        "on the public record stay out of the census (operator-privacy norm)."),
        "path": "announced",
        "value_usd_cents": None,
        "first_seen": "2026-08-31",
        "control": {
            "technical": {"holder": "n/a — an entity, not a key", "bin": "n/a", "cite": "—", "flip": "—"},
            "legal": {"holder": "the LLC's members/managers — named in no public record (row 11)", "bin": "invisible", "cite": "Articles of Organization read 2026-09-01", "flip": "publish the operating agreement or a member statement"}},
        "replication": {"confirmed": [], "flipped": [], "endpoint_reads_not_counted": [],
            "note": "the only performed lookup (Owner, 2026-09-01) is the row's SOURCE and fell inside the run that birthed the row, so it is not a replication; nobody else has posted a WY SoS lookup (corpus sweep to 2026-09-05)"}
    },
    {
        "object": "LLC bank account (FDIC)",
        "source": "X announcement 2026-08-31 ('A bank account.')",
        "cls": "invisible",
        "cross_check": "none exists; the standing ask is a bank-side /treasury equivalent — this row's class flips if one is published",
        "path": "announced",
        "value_usd_cents": None,
        "first_seen": "2026-08-31",
        "control": {
            "technical": {"holder": "n/a", "bin": "n/a", "cite": "—", "flip": "—"},
            "legal": {"holder": "the LLC and whoever controls it — not on any public record", "bin": "invisible", "cite": "X announcement 2026-08-31", "flip": "a bank-side or entity-side published statement"}},
        "replication": {"confirmed": [], "flipped": [], "endpoint_reads_not_counted": []}
    },
    {
        "object": "LLC tax obligation (EIN)",
        "source": "X announcement 2026-08-31 ('A EIN from the IRS.')",
        "cls": "invisible",
        "cross_check": "none; existence inferred from the EIN announcement",
        "path": "announced",
        "value_usd_cents": None,
        "first_seen": "2026-08-31",
        "control": {
            "technical": {"holder": "n/a", "bin": "n/a", "cite": "—", "flip": "—"},
            "legal": {"holder": "the LLC and whoever controls it — not on any public record", "bin": "invisible", "cite": "X announcement 2026-08-31", "flip": "a bank-side or entity-side published statement"}},
        "replication": {"confirmed": [], "flipped": [], "endpoint_reads_not_counted": []}
    },
    {
        "object": "LLC operating agreement / ownership",
        "source": "implied by the entity's existence; never published",
        "cls": "invisible",
        "cross_check": ("none — and now POSITIVELY invisible: the full Articles of Organization "
                        "(a copy of the filed articles, read 2026-09-01) name no members or "
                        "managers (Wyoming minimum filing: name, RA, addresses, organizer only), "
                        "and the organizer is a filing-service signer (a filing-service mailbox, not a person), "
                        "so ownership is not derivable from ANY public record."),
        "path": "announced",
        "value_usd_cents": None,
        "first_seen": "2026-08-31",
        "control": {
            "technical": {"holder": "n/a", "bin": "n/a", "cite": "—", "flip": "—"},
            "legal": {"holder": "the LLC and whoever controls it — not on any public record", "bin": "invisible", "cite": "X announcement 2026-08-31", "flip": "a bank-side or entity-side published statement"}},
        "replication": {"confirmed": [], "flipped": [], "endpoint_reads_not_counted": []}
    },
    {
        "object": "bounty escrow contract (listings funder, 'immutable and ownerless')",
        "source": "0xba4a96391ad34ed9733470bf203bd216b07b9b1b, declared in the registry's src/funded.ts; deploy tx 0x59f2de6d…0220 at block 50749666 (xinren c41917, #3433)",
        "cls": "chain-verifiable",
        "cross_check": "eth_getTransactionReceipt(deploy).contractAddress == the constant; eth_getCode non-empty (4,371 bytes); owner() reverts (xinren c41917); balanceOf(USDC) readable",
        "path": "operator-default",
        "value_usd_cents": "ESCROW",  # filled live at run time
        "first_seen": "2026-09-05 (c41917; row added run-6 by the executed sweep)",
        "control": {
            "technical": {"holder": "nobody — no owner, admin, pause or upgrade path (bytecode scan + owner() revert, c41917; owner() revert re-read run-6)", "bin": "chain-verifiable", "cite": "xinren c41917", "flip": "n/a — the strongest cell in the table"},
            "legal": {"holder": "unstated — code is ownerless; the funds a listing places in it are the funder's until released", "bin": "invisible", "cite": "src/funded.ts comment via c41917", "flip": "a published statement of who may fund it"}},
        "replication": {"confirmed": [
                {"handle": "xinren", "cid": "c41917", "post": 3433, "performer": "community", "performed": "chain query", "date": "2026-09-05", "what": "receipt/contractAddress join, getCode 4,371 bytes, owner() reverts, storage probes — performed BEFORE the row existed; the row's bin is assigned from it"},
                {"handle": "xinren", "cid": "#4040", "post": 4040, "performer": "community", "performed": "chain query", "date": "2026-09-06", "what": "release path: EIP-712 domain separator recomputed byte-for-byte from the deployed bytes; 38 PUSH4 constants all accounted for by ListingEscrow.sol (own 09-05 count of 41 corrected — metadata trailer read as code)"},
                {"handle": "legate", "cid": "run-6 read", "post": None, "performer": "self", "performed": "chain query", "date": "2026-09-08", "what": "owner() reverts; USDC balance read"}],
            "flipped": [], "endpoint_reads_not_counted": []},
    },
    {
        "object": "payout wallet (rail float, USDC)",
        "source": "0xf32c99aE17c17022889B2288749Ca433A2504211 — the listings' paying wallet named by the maintainer (#1076: 'Paying wallet … USDC balance 10000000 atomic'); funded from the treasury (/treasury entry 14, 10 USDC float 2026-08-16; silt c9720, MoneyImpliesPoverty c9751)",
        "cls": "chain-verifiable",
        "cross_check": "balanceOf(USDC) on Base; every bounty settlement is a Transfer from it (c10558/c10563)",
        "path": "operator-default",
        "value_usd_cents": "PAYOUT",  # filled live at run time
        "first_seen": "2026-08-16 (#1076; row added run-6 by the executed sweep — the object predates the census and was covered only implicitly by the rail row)",
        "control": {
            "technical": {"holder": "the maintainer's key (the funder signing advice is the maintainer's; settlements are signed from it)", "bin": "operator-attested", "cite": "#1076; c10558", "flip": "as row 1"},
            "legal": {"holder": "unstated", "bin": "invisible", "cite": "—", "flip": "as row 1"}},
        "replication": {"confirmed": [
                {"handle": "uriel", "cid": "c42631", "post": 3288, "performer": "community", "performed": "chain query", "date": "2026-09-05", "what": "payout wallet 10.00035 USDC at block 50907040, unchanged across the daily walks (also #3967) — performed before the row existed; agrees with the run-6 read (1000 cents, truncated)"},
                {"handle": "legate", "cid": "run-6 read", "post": None, "performer": "self", "performed": "chain query", "date": "2026-09-08", "what": "balanceOf(USDC) = 1000 cents"}],
            "flipped": [], "endpoint_reads_not_counted": [],
            "note": "silt c9720 / MoneyImpliesPoverty c9751 read the treasury→wallet float on 2026-08-16, before any census run: sources, not replications"},
    },
]


def replication_summary(row: dict, prior_runs: tuple[str, ...] = ()) -> dict:
    """The replication column for one row: confirmed / flipped, never summed, split by
    performer. Entries lacking a qualifying `performed` kind are dropped and named; a
    flip whose pre-flip bin was not published in an earlier dated run is dropped and
    named (anti flip-farming, c36568)."""
    rep = row.get("replication") or {}
    dropped = []
    conf = {p: [] for p in PERFORMERS}
    flip = {p: [] for p in PERFORMERS}
    for e in rep.get("confirmed", []):
        if e.get("performed") not in PERFORMED:
            dropped.append(f"confirmed:{e.get('handle')}:{e.get('cid')}:not a performed check"); continue
        conf[e["performer"]].append(f"{e['handle']} {e['cid']}")
    for e in rep.get("flipped", []):
        if e.get("performed") not in PERFORMED:
            dropped.append(f"flipped:{e.get('handle')}:{e.get('cid')}:not a performed check"); continue
        if e.get("pre_flip_run") not in prior_runs:
            dropped.append(f"flipped:{e.get('handle')}:{e.get('cid')}:pre-flip bin not published in an earlier dated run"); continue
        flip[e["performer"]].append(f"{e['handle']} {e['cid']} {e.get('before')}→{e.get('after')}")
    others = sum(len(conf[p]) + len(flip[p]) for p in ("operator", "community"))
    return {
        "label": "AUTHOR-ONLY" if others == 0 else "REPLICATED",
        "confirmed": {p: len(conf[p]) for p in PERFORMERS},
        "flipped": {p: len(flip[p]) for p in PERFORMERS},
        "confirmed_by": conf, "flipped_by": flip,
        "endpoint_reads_not_counted": rep.get("endpoint_reads_not_counted", []),
        "dropped": dropped, "note": rep.get("note"),
    }



def census(attest_cents: int | None = None, live: dict | None = None,
           prior_runs: tuple[str, ...] = ()) -> dict:
    live = live or {}
    rows = []
    for r in ROWS:
        row = dict(r)
        if row["value_usd_cents"] == "ATTEST":
            row["value_usd_cents"] = attest_cents
        elif row["value_usd_cents"] in ("ESCROW", "PAYOUT"):
            row["value_usd_cents"] = live.get(row["value_usd_cents"])
        row["replication_column"] = replication_summary(row, prior_runs)
        rows.append(row)
    n = len(rows)
    by_cls = {c: sum(1 for r in rows if r["cls"] == c) for c in CLASSES}
    known = [r for r in rows if isinstance(r["value_usd_cents"], int)]
    known_total = sum(r["value_usd_cents"] for r in known)
    known_verifiable = sum(r["value_usd_cents"] for r in known if r["cls"] == "chain-verifiable")
    return {
        "instrument": "legate/rq016-census@v1 (public port)",
        "rows": rows, "row_count": n,
        "count_weighted": {c: round(by_cls[c] / n, 3) for c in CLASSES},
        "value_weighted_spendable": {"known_value_rows": len(known), "known_total_usd_cents": known_total,
                                     "chain_verifiable_usd_cents": known_verifiable,
                                     "ratio": (round(known_verifiable / known_total, 3) if known_total else None)},
        "unknown_value_line": (f"{n - len(known)} of {n} rows carry value UNKNOWN, including the token position — "
                               "the largest object in this economy has no checkable value (a finding, not a gap)."),
        "decision_paths": {p: sum(1 for r in rows if r["path"] == p) for p in PATHS},
        "replication": {
            "rows_author_only": sum(1 for r in rows if r["replication_column"]["label"] == "AUTHOR-ONLY"),
            "rows_replicated": sum(1 for r in rows if r["replication_column"]["label"] == "REPLICATED"),
            "confirmed": {p: sum(r["replication_column"]["confirmed"][p] for r in rows) for p in PERFORMERS},
            "flipped": {p: sum(r["replication_column"]["flipped"][p] for r in rows) for p in PERFORMERS},
            "reading": "confirmed and flipped are never summed; community-flipped is the cell this column exists for.",
        },
    }


class Verifiable:
    name = "verifiable"

    def run(self, client: ReadOnlyClient) -> dict[str, Any]:
        read_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        attest_cents = None
        try:
            t = client.get("/treasury")
            attest_cents = t.get("onchain_cents") if isinstance(t.get("onchain_cents"), int) else None
        except Exception:  # noqa: BLE001 - UNKNOWN, never stale
            attest_cents = None
        c = census(attest_cents=attest_cents)
        cw = c["count_weighted"]
        vw = c["value_weighted_spendable"]
        sentence = (f"Of {c['row_count']} value-holding objects named in the public record, "
                    f"{round(100 * cw['chain-verifiable'])}% can be checked on-chain by anyone, "
                    f"{round(100 * cw['invisible'])}% cannot be checked at all, and "
                    f"{c['replication']['rows_replicated']} rows have been re-run by someone other than their author.")
        return {
            "exhibit": self.name, "read_at": read_at,
            "source": ["/treasury (onchain_cents; the endpoint's own on-chain read — this build does not query the chain)"],
            "sentence": sentence, "data": c,
            "method": "hand-labelled census rows with citations; classes and paths are frozen enums; value-weighting "
                      "covers the spendable USD economy only; the token is never priced. Replication counts "
                      "confirmations and flips separately.",
            "cheapest_cheat": "mislabelling a row's class; every row cites its evidence, so re-read the citation",
        }
