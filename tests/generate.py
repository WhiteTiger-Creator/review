"""Held-out pool population, rebuilt here from a fixed seed at grading time.

Nothing generated here ships in the task image. The pools use the same record
shape as the worked samples, sized so that every one of them exercises the
reclaim ladder, shared extents that only a run of releases can free, and ids
handed out in an order that is not the taken order.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

import reference

EPOCH = datetime(2026, 1, 5, 0, 0, 0, tzinfo=timezone.utc)  # a Monday
SEED = 20260731
COUNT = 40


def stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_pool(rng: random.Random, name: str) -> dict:
    count = rng.randint(9, 16)
    moment = EPOCH + timedelta(days=rng.randint(0, 40), hours=rng.randint(0, 20))
    labels = [f"{name}-s{i:02d}" for i in range(count)]
    rng.shuffle(labels)
    snaps = []
    for index in range(count):
        # Mixed gaps: some inside one hour, some inside one day, some weeks
        # apart, so every tier holds periods with more than one snapshot.
        gap = rng.choice([15, 40, 95, 300, 700, 1500, 4000, 11000])
        moment = moment + timedelta(minutes=gap)
        snap = {"id": labels[index], "taken": stamp(moment)}
        if rng.random() < 0.14:
            snap["hold_until"] = stamp(moment + timedelta(days=rng.randint(40, 400)))
        if rng.random() < 0.12:
            snap["clone"] = True
        snaps.append(snap)
    now = stamp(moment + timedelta(hours=rng.randint(1, 30)))

    extents = []
    for _ in range(rng.randint(14, 26)):
        first = rng.randrange(count)
        span = rng.choice([0, 0, 1, 1, 2, 3, 4])
        last = min(count - 1, first + span)
        extents.append(
            {
                "blocks": rng.randint(5, 900),
                "first": first,
                "last": last,
                "live": rng.random() < 0.22,
            }
        )

    pool = {
        "pool": name,
        "now": now,
        "keep": {
            "hourly": rng.randint(0, 3),
            "daily": rng.randint(1, 4),
            "weekly": rng.randint(0, 3),
            "monthly": rng.randint(0, 2),
        },
        "target_blocks": 0,
        "snapshots": snaps,
        "extents": extents,
    }
    pool["target_blocks"] = pick_target(rng, pool)
    return pool


def pick_target(rng: random.Random, pool: dict) -> int:
    """A target that makes the pool walk the ladder rather than stop at once."""
    if rng.random() < 0.15:
        # Out of reach even at the bottom of the ladder, so the run reports a
        # shortfall.
        return sum(extent["blocks"] for extent in pool["extents"]) + 1
    anchor = reference.anchors(pool)
    keep = dict(pool["keep"])
    curve = []
    while True:
        retained = reference.retained_set(pool, keep, anchor)
        curve.append(reference.freed_blocks(pool, retained))
        nxt = reference.ladder(keep)
        if nxt is None:
            break
        keep = nxt
    steps = [i for i in range(1, len(curve)) if curve[i] > curve[0]]
    if not steps:
        return curve[0]
    step = rng.choice(steps)
    return curve[step - 1] + 1 if curve[step] > curve[step - 1] else curve[step]


def graded_pools(seed: int = SEED, count: int = COUNT) -> list[dict]:
    rng = random.Random(seed)
    return [build_pool(rng, f"pool{index:02d}") for index in range(count)]
