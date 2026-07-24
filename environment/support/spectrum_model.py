"""Offline numeric helpers for culvert affinity diagnostics.

These helpers do not implement window coupling, partition selection, or rank binding.
"""

from __future__ import annotations

import hashlib
import math

SIGMA = 1.25


def affinity(points: list[list[float]]) -> list[list[float]]:
    n = len(points)
    w = [[0.0] * n for _ in range(n)]
    denom = 2.0 * SIGMA * SIGMA
    for i in range(n):
        for j in range(i + 1, n):
            dist = sum((points[i][d] - points[j][d]) ** 2 for d in range(len(points[i])))
            val = math.exp(-dist / denom)
            w[i][j] = w[j][i] = val
    return w


def laplacian(w: list[list[float]]) -> list[list[float]]:
    n = len(w)
    deg = [sum(row) for row in w]
    return [[deg[i] if i == j else -w[i][j] for j in range(n)] for i in range(n)]


def smallest_eigs(lap: list[list[float]], count: int) -> list[float]:
    n = len(lap)
    a = [row[:] for row in lap]
    vecs = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    vals: list[float] = []
    for k in range(count):
        v = vecs[k]
        for _ in range(40):
            y = [sum(a[i][j] * v[j] for j in range(n)) for i in range(n)]
            norm = math.sqrt(sum(x * x for x in y))
            if norm < 1e-12:
                break
            v = [x / norm for x in y]
        num = sum(v[i] * sum(a[i][j] * v[j] for j in range(n)) for i in range(n))
        den = sum(x * x for x in v)
        vals.append(num / den)
        for i in range(n):
            for j in range(n):
                a[i][j] -= vals[-1] * v[i] * v[j]
    return vals


def group_digest_for(rank_order: list[str]) -> str:
    h = hashlib.sha256()
    for item in rank_order:
        h.update(item.encode())
    return h.hexdigest()[:16]


def parse_rank_yaml(text: str) -> dict:
    record: dict = {}
    lines = text.splitlines()
    idx = 0
    pc_key = "partition_count:"
    while idx < len(lines):
        line = lines[idx].strip()
        if line.startswith("profile:"):
            record["profile"] = line.split(":", 1)[1].strip()
        elif line.startswith(pc_key):
            record["partition_count"] = int(line.split(":", 1)[1].strip())
        elif line.startswith("spectral_span:"):
            record["spectral_span"] = float(line.split(":", 1)[1].strip())
        elif line.startswith("group_digest:"):
            record["group_digest"] = line.split(":", 1)[1].strip()
        elif line == "rank_order:":
            order = []
            idx += 1
            while idx < len(lines) and lines[idx].startswith("- "):
                order.append(lines[idx].strip()[2:])
                idx += 1
            record["rank_order"] = order
            continue
        idx += 1
    return record
