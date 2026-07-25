"""Restore cargo vendor dotfiles stripped by TB3 package_task.

Reads environment/vendor_meta/<crate>__{checksum,vcs}.json and writes
.cargo-checksum.json / .cargo_vcs_info.json under each vendor crate.

Also prunes .cargo-checksum.json file maps to paths that exist on disk:
package_task excludes dotdirs such as .github/, so those entries must not
remain in the checksum or offline cargo build fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def restore(vendor: Path, meta: Path) -> int:
    count = 0
    for path in sorted(meta.glob("*.json")):
        name = path.name
        if name.endswith("__checksum.json"):
            crate = name[: -len("__checksum.json")]
            target_name = ".cargo-checksum.json"
        elif name.endswith("__vcs.json"):
            crate = name[: -len("__vcs.json")]
            target_name = ".cargo_vcs_info.json"
        else:
            raise SystemExit(f"unexpected vendor_meta file: {name}")
        crate_dir = vendor / crate.replace("__", "/")
        if not crate_dir.is_dir():
            raise SystemExit(f"vendor crate missing for meta {name}: {crate_dir}")
        (crate_dir / target_name).write_bytes(path.read_bytes())
        count += 1
    return count


def prune_checksums(vendor: Path) -> int:
    pruned = 0
    for checksum in vendor.glob("*/.cargo-checksum.json"):
        data = json.loads(checksum.read_text(encoding="utf-8"))
        files = data.get("files", {})
        kept = {}
        removed = 0
        for rel, digest in files.items():
            if (checksum.parent / rel).is_file():
                kept[rel] = digest
            else:
                removed += 1
        if removed:
            data["files"] = kept
            checksum.write_text(
                json.dumps(data, separators=(",", ":")),
                encoding="utf-8",
            )
            pruned += 1
    return pruned


def main() -> int:
    vendor = Path(sys.argv[1] if len(sys.argv) > 1 else "/app/environment/vendor")
    meta = Path(sys.argv[2] if len(sys.argv) > 2 else "/app/environment/vendor_meta")
    if not vendor.is_dir():
        print(f"vendor directory missing: {vendor}", file=sys.stderr)
        return 1
    if not meta.is_dir():
        print(f"vendor_meta directory missing: {meta}", file=sys.stderr)
        return 1
    n = restore(vendor, meta)
    p = prune_checksums(vendor)
    print(f"restored {n} vendor cargo metadata files; pruned checksums in {p} crates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
