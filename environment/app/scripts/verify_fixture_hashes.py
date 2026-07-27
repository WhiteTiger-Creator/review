#!/usr/bin/env python3
import hashlib
import json
import sys
from pathlib import Path

manifest = json.loads(Path("/app/docs/trusted-fixtures.json").read_text())
for rel, expected in manifest.get("files", {}).items():
    p = Path("/app") / rel
    if not p.exists():
        print(f"missing {rel}", file=sys.stderr)
        sys.exit(1)
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    if digest != expected:
        print(f"hash mismatch {rel}", file=sys.stderr)
        sys.exit(1)
print("fixture integrity ok")
