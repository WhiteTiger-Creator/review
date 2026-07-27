#!/usr/bin/env python3
"""Check a registry directory the way ingest does, without building anything.

    ./tools/registry-lint.py [registry-dir]

Reports one line per package and exits non-zero when a file would be rejected.
"""
import json
import pathlib
import re
import sys

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(-rc\.[1-9]\d*)?$")


def check(path):
    problems = []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{path.name}: not JSON ({exc})"], 0
    if doc.get("name") != path.stem:
        problems.append(f"{path.name}: name {doc.get('name')!r} does not match the file stem")
    releases = doc.get("releases") or []
    if not releases:
        problems.append(f"{path.name}: no releases")
    seen = set()
    for rel in releases:
        version = rel.get("version", "")
        if not VERSION_RE.match(version):
            problems.append(f"{path.name}: bad version {version!r}")
        if version in seen:
            problems.append(f"{path.name}: duplicate version {version}")
        seen.add(version)
        edges = list(rel.get("requires") or [])
        for reqs in (rel.get("features") or {}).values():
            edges.extend(reqs)
        for edge in edges:
            if not edge.get("name") or not edge.get("range"):
                problems.append(f"{path.name}: {version} has an incomplete edge")
    return problems, len(releases)


def main():
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/app/registry")
    files = sorted(root.glob("*.json"))
    if not files:
        print(f"no package files under {root}", file=sys.stderr)
        return 1
    bad = 0
    for path in files:
        problems, count = check(path)
        if problems:
            bad += 1
            for line in problems:
                print(line, file=sys.stderr)
        else:
            print(f"ok {path.stem} releases={count}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
