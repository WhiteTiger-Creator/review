"""Deterministic tar archive construction for verifier tests."""

from __future__ import annotations

import hashlib
import io
import random
import tarfile
from dataclasses import dataclass
from typing import Any


@dataclass
class Injection:
    path: str
    kind: str
    rule_id: str
    line: int


def build_archive(seed: int, injections: list[dict[str, Any]]) -> tuple[bytes, list[Injection]]:
    rng = random.Random(seed)
    manifest: list[Injection] = []
    entries: list[tuple[str, bytes, int, str, str]] = []
    for spec in injections:
        path = spec.get("path") or f"payload/{rng.randint(1000, 9999)}/{spec['name']}"
        data = spec["data"].encode() if isinstance(spec["data"], str) else spec["data"]
        entries.append((path, data, 1718452800, spec.get("type", "file"), spec.get("linkname", "")))
        if spec.get("expect_finding"):
            manifest.append(
                Injection(path=path, kind=spec.get("kind", "secret"), rule_id=spec["rule_id"], line=spec.get("line", 1))
            )
    rng.shuffle(entries)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.USTAR_FORMAT) as tf:
        for name, data, mtime, entry_type, linkname in entries:
            info = tarfile.TarInfo(name=name)
            info.mtime = mtime
            info.mode = 0o644
            info.uid = 1000
            info.gid = 1000
            info.uname = "app"
            info.gname = "app"
            if entry_type == "file":
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
            else:
                typeflags = {
                    "symlink": tarfile.SYMTYPE,
                    "hardlink": tarfile.LNKTYPE,
                    "fifo": tarfile.FIFOTYPE,
                }
                info.type = typeflags[entry_type]
                info.linkname = linkname
                info.size = 0
                tf.addfile(info)
    return buf.getvalue(), manifest


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
