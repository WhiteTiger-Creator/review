#!/usr/bin/env python3
import hashlib
import json
import sys
from pathlib import Path

manifest = json.loads(Path("/app/docs/trusted-fixtures.json").read_text())
for rel, expected in manifest.get("files", {}).items():
    digest = hashlib.sha256((Path("/app") / rel).read_bytes()).hexdigest()
    if digest != expected:
        print(f"mismatch {rel}", file=sys.stderr)
        sys.exit(1)
print("fixture hashes ok")
