"""Independent reference for the snapshot reclaim supervisor.

Written from the operator manual in /app/PROTOCOL.md in a different language
than the candidate implementation. Used by the suite to compute expected
reports for the graded pools and by the generator to produce the shipped
samples.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone

TIERS = ("hourly", "daily", "weekly", "monthly")
TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class FatalInput(Exception):
    """The pool record is not admissible; the supervisor exits nonzero."""


def parse_ts(value: str) -> datetime:
    if not isinstance(value, str) or not TS.match(value):
        raise FatalInput(f"bad timestamp {value!r}")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise FatalInput(f"bad timestamp {value!r}") from exc


def period_key(tier: str, taken: str) -> str:
    """The period a snapshot belongs to, in the tier's key form."""
    if tier == "hourly":
        return taken[:13]
    if tier == "daily":
        return taken[:10]
    if tier == "monthly":
        return taken[:7]
    day = parse_ts(taken)
    monday = day - timedelta(days=day.weekday())
    return monday.strftime("%Y-%m-%d")


def validate(pool: dict) -> None:
    if not isinstance(pool.get("pool"), str) or not pool["pool"]:
        raise FatalInput("pool name missing")
    snaps = pool.get("snapshots")
    if not isinstance(snaps, list) or not snaps:
        raise FatalInput("snapshots missing")
    parse_ts(pool.get("now", ""))
    seen: set[str] = set()
    previous = None
    for snap in snaps:
        sid = snap.get("id")
        if not isinstance(sid, str) or not sid:
            raise FatalInput("snapshot id missing")
        if sid in seen:
            raise FatalInput(f"duplicate snapshot id {sid}")
        seen.add(sid)
        taken = parse_ts(snap.get("taken", ""))
        if previous is not None and taken <= previous:
            raise FatalInput("snapshots not in strictly increasing taken order")
        previous = taken
        if snap.get("hold_until"):
            parse_ts(snap["hold_until"])
    keep = pool.get("keep")
    if not isinstance(keep, dict):
        raise FatalInput("keep missing")
    for tier in TIERS:
        value = keep.get(tier)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise FatalInput(f"keep.{tier} invalid")
    target = pool.get("target_blocks")
    if not isinstance(target, int) or isinstance(target, bool) or target < 0:
        raise FatalInput("target_blocks invalid")
    extents = pool.get("extents")
    if not isinstance(extents, list):
        raise FatalInput("extents missing")
    for extent in extents:
        blocks = extent.get("blocks")
        first = extent.get("first")
        last = extent.get("last")
        if not isinstance(blocks, int) or isinstance(blocks, bool) or blocks <= 0:
            raise FatalInput("extent blocks invalid")
        for index in (first, last):
            if not isinstance(index, int) or isinstance(index, bool):
                raise FatalInput("extent index invalid")
            if index < 0 or index >= len(snaps):
                raise FatalInput("extent index out of range")
        if first > last:
            raise FatalInput("extent first after last")
        if not isinstance(extent.get("live"), bool):
            raise FatalInput("extent live invalid")


def anchors(pool: dict) -> dict[int, str]:
    """Snapshots retained regardless of the tier counts, with their class."""
    now = parse_ts(pool["now"])
    out: dict[int, str] = {}
    for index, snap in enumerate(pool["snapshots"]):
        if snap.get("hold_until") and parse_ts(snap["hold_until"]) > now:
            out[index] = "hold"
        elif snap.get("clone") is True:
            out[index] = "clone"
    return out


def representatives(pool: dict, tier: str) -> dict[str, int]:
    """The earliest snapshot taken in each period of this tier."""
    out: dict[str, int] = {}
    for index, snap in enumerate(pool["snapshots"]):
        key = period_key(tier, snap["taken"])
        if key not in out:
            out[key] = index
    return out


def retained_set(pool: dict, keep: dict[str, int], anchor: dict[int, str]) -> dict[int, str]:
    """Anchors plus the tier representatives that consume a keep slot."""
    out: dict[int, str] = dict(anchor)
    for tier in TIERS:
        slots = keep[tier]
        if slots <= 0:
            continue
        reps = representatives(pool, tier)
        for key in sorted(reps, reverse=True):
            index = reps[key]
            if index in anchor:
                continue
            if index not in out:
                out[index] = tier
            slots -= 1
            if slots == 0:
                break
    return out


def freed_blocks(pool: dict, retained: dict[int, str]) -> int:
    """Blocks released by deleting every snapshot outside the retained set."""
    total = 0
    for extent in pool["extents"]:
        if extent["live"]:
            continue
        if all(index not in retained for index in range(extent["first"], extent["last"] + 1)):
            total += extent["blocks"]
    return total


def ladder(keep: dict[str, int]) -> dict[str, int] | None:
    """One relaxation step, or None once every tier count is zero."""
    for tier in TIERS:
        if keep[tier] > 0:
            out = dict(keep)
            out[tier] -= 1
            return out
    return None


def plan_pool(pool: dict) -> dict:
    validate(pool)
    anchor = anchors(pool)
    keep = {tier: pool["keep"][tier] for tier in TIERS}
    target = pool["target_blocks"]
    passes = 0
    while True:
        retained = retained_set(pool, keep, anchor)
        freed = freed_blocks(pool, retained)
        if freed >= target:
            break
        relaxed = ladder(keep)
        if relaxed is None:
            break
        keep = relaxed
        passes += 1
    snaps = pool["snapshots"]
    retained_rows = [
        {"id": snaps[index]["id"], "class": retained[index]}
        for index in range(len(snaps))
        if index in retained
    ]
    pruned = [snaps[index]["id"] for index in range(len(snaps)) if index not in retained]
    shortfall = target - freed if target > freed else 0
    row = {
        "pool": pool["pool"],
        "passes": passes,
        "keep_final": {tier: keep[tier] for tier in TIERS},
        "retained": retained_rows,
        "pruned": pruned,
        "freed_blocks": freed,
        "shortfall": shortfall,
    }
    row["digest"] = pool_digest(row)
    return row


def pool_digest(row: dict) -> str:
    keep = row["keep_final"]
    payload = "\n".join(
        [
            row["pool"],
            str(row["passes"]),
            "{},{},{},{}".format(keep["hourly"], keep["daily"], keep["weekly"], keep["monthly"]),
            ";".join(f"{item['id']}:{item['class']}" for item in row["retained"]),
            ";".join(row["pruned"]),
            str(row["freed_blocks"]),
            str(row["shortfall"]),
        ]
    ) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def plan(pools: list[dict]) -> dict:
    names = [pool.get("pool") for pool in pools]
    if len(set(names)) != len(names):
        raise FatalInput("duplicate pool name")
    rows = sorted((plan_pool(pool) for pool in pools), key=lambda row: row["pool"])
    payload = "".join(f"{row['pool']} {row['digest']}\n" for row in rows)
    return {"pools": rows, "digest": hashlib.sha256(payload.encode("utf-8")).hexdigest()}
