"""SoftHSM fixtures used only to exercise ambiguous legacy selection."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

MODULE = "/usr/lib/softhsm/libsofthsm2.so"


def _run(args: list[str], env: dict[str, str]) -> None:
    result = subprocess.run(args, env=env, text=True, capture_output=True, check=False)
    assert result.returncode == 0, f"{args[0]} failed:\n{result.stdout}\n{result.stderr}"


def create_ambiguous_legacy_token(root: Path, pin: str = "123456") -> tuple[Path, Path]:
    """Create a token holding two private keys with the same legacy label."""
    store = root / "tokens"
    store.mkdir(parents=True)
    conf = root / "softhsm2.conf"
    conf.write_text(f"directories.tokendir = {store}\nobjectstore.backend = file\nlog.level = ERROR\n")
    env = {**os.environ, "SOFTHSM2_CONF": str(conf)}
    _run(["softhsm2-util", "--init-token", "--free", "--label", "legacy-token",
          "--serial", "9001", "--so-pin", "87654321", "--pin", pin], env)
    for key_id in ("01", "02"):
        _run(["pkcs11-tool", "--module", MODULE, "--token-label", "legacy-token",
              "--login", "--pin", pin, "--keypairgen", "--key-type", "rsa:2048",
              "--label", "legacy-signing", "--id", key_id, "--usage-sign"], env)
    return conf, store
