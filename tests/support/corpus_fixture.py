"""Unpack hidden corpus fixtures for verifier sessions."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
METADATA = Path(__file__).resolve().parent / "corpus_metadata.json"


def unpack(name: str, dest_parent: Path | None = None) -> Path:
    archive = FIXTURES / f"{name}.tar.zst"
    if not archive.exists():
        raise FileNotFoundError(archive)
    parent = dest_parent or Path(tempfile.mkdtemp(prefix=f"corpus-{name}-"))
    import io
    import tarfile

    try:
        import zstandard as zstd
    except ImportError:
        raise RuntimeError("zstandard package required for fixture unpacking")
    payload = zstd.ZstdDecompressor().decompress(archive.read_bytes())
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as tf:
        tf.extractall(parent)
    children = [p for p in parent.iterdir() if p.is_dir()]
    if len(children) != 1:
        raise RuntimeError(f"expected one corpus directory in {archive}")
    repo = children[0]
    subprocess.run(
        ["git", "config", "--global", "--add", "safe.directory", str(repo.resolve())],
        check=False,
    )
    os.chmod(repo, 0o555)
    for root, dirs, files in os.walk(repo):
        for d in dirs:
            os.chmod(Path(root) / d, 0o555)
        for f in files:
            os.chmod(Path(root) / f, 0o444)
    return repo


def metadata() -> dict:
    return json.loads(METADATA.read_text(encoding="utf-8"))
