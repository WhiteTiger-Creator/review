"""Narrow verifier helpers shared by the candidate-facing tests.

No end-to-end planner or SQL renderer lives here. These are strictly bounded
diagnostic and lookup utilities: sha256 digests, a capped structural JSON
diff, human-readable byte-mismatch reports, and small row-lookup helpers.
"""

from __future__ import annotations

import hashlib
from typing import Any

MAX_DIFFS = 8


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_diff(
    expected: Any, actual: Any, path: str = "$", limit: int = MAX_DIFFS
) -> list[str]:
    """Recursively diff two JSON-like structures, returning up to ``limit`` mismatches."""
    out: list[str] = []

    def walk(exp: Any, act: Any, at: str) -> None:
        if len(out) >= limit:
            return
        if isinstance(exp, dict) and isinstance(act, dict):
            for key in sorted(set(exp) | set(act)):
                if len(out) >= limit:
                    return
                if key not in exp:
                    out.append(
                        f"{at}.{key}: missing in expected, actual={act.get(key)!r}"
                    )
                elif key not in act:
                    out.append(
                        f"{at}.{key}: missing in actual, expected={exp.get(key)!r}"
                    )
                else:
                    walk(exp[key], act[key], f"{at}.{key}")
        elif isinstance(exp, list) and isinstance(act, list):
            if len(exp) != len(act):
                out.append(f"{at}: length expected={len(exp)} actual={len(act)}")
                return
            for i, (exp_item, act_item) in enumerate(zip(exp, act, strict=False)):
                if len(out) >= limit:
                    return
                walk(exp_item, act_item, f"{at}[{i}]")
        elif exp != act:
            out.append(f"{at}: expected={exp!r} actual={act!r}")

    walk(expected, actual, path)
    return out[:limit]


def format_plan_diff_report(expected: dict[str, Any], actual: dict[str, Any]) -> str:
    """Bounded, readable explanation for a plan JSON mismatch (max 8 diffs)."""
    diffs = json_diff(expected, actual)
    if not diffs:
        return "plan JSON differs but no structural diff could be located"
    return "plan JSON differs:\n" + "\n".join(diffs)


def format_sql_diff_report(expected: bytes, actual: bytes) -> str:
    """Bounded, readable explanation for a SQL byte-mismatch (first differing byte/line)."""
    limit = min(len(expected), len(actual))
    offset = -1
    for i in range(limit):
        if expected[i] != actual[i]:
            offset = i
            break
    if offset == -1 and len(expected) != len(actual):
        offset = limit

    lines = [
        f"sql byte mismatch (expected {len(expected)} bytes, actual {len(actual)} bytes)"
    ]
    if offset != -1:
        exp_b = expected[offset] if offset < len(expected) else None
        act_b = actual[offset] if offset < len(actual) else None
        lines.append(
            f"first differing byte offset: {offset} expected={exp_b!r} actual={act_b!r}"
        )

    exp_lines = expected.decode("utf-8", "replace").splitlines()
    act_lines = actual.decode("utf-8", "replace").splitlines()
    for i in range(max(len(exp_lines), len(act_lines))):
        e = exp_lines[i] if i < len(exp_lines) else "<eof>"
        a = act_lines[i] if i < len(act_lines) else "<eof>"
        if e != a:
            lines.append(
                f"first differing line {i + 1}:\nexpected: {e!r}\nactual:   {a!r}"
            )
            break
    return "\n".join(lines)


def find_cluster(plan: dict[str, Any], cluster_id: str) -> dict[str, Any]:
    for row in plan["cluster_rows"]:
        if row["cluster_id"] == cluster_id:
            return row
    raise AssertionError(f"missing cluster_rows[{cluster_id}]")


def find_row(rows: list[dict[str, Any]], **filters: Any) -> dict[str, Any]:
    """Return the sole row in ``rows`` matching every ``field=value`` filter."""
    for row in rows:
        if all(row.get(key) == value for key, value in filters.items()):
            return row
    raise AssertionError(f"no row matches filters {filters!r}")
