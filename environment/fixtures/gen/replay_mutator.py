"""Deterministic held-out ref rename for replay tests."""
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("src")
    p.add_argument("dst")
    p.add_argument("--release-ref", default="release")
    p.add_argument("--alt-name", default="ship_line")
    args = p.parse_args()
    src = Path(args.src)
    dst = Path(args.dst)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    subprocess.check_call(
        ["git", "-C", str(dst), "branch", "-m", args.release_ref, args.alt_name],
        stdout=subprocess.DEVNULL,
    )


if __name__ == "__main__":
    main()
