import subprocess
from pathlib import Path

APP = Path("/app")
ADMIN = APP / "usr/sbin/site-admin"
ACTIVATE = APP / "usr/sbin/site-activate"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def make_state(tmp_path: Path, *, pending: str = "drop:retired/link\n") -> Path:
    root = tmp_path / "target"
    write(root / "payload/alpha.txt", "alpha payload\n")
    write(root / "payload/nested/beta.txt", "nested payload\n")
    write(root / "namespace/retired/link", "old namespace entry\n")
    write(root / ".site/busy", "0\n")
    write(root / ".site/sequence", "0\n")
    write(root / ".site/pending", pending)
    write(root / ".site/status", "prepared\n")
    write(root / ".site/ready", "")
    write(root / ".site/account", "count=99\nfingerprint=stale\ngeneration=1\n")
    return root


def run(entry: Path, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(entry), str(root)],
        text=True,
        capture_output=True,
        check=False,
    )


def run_core(action: str, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/app/bin/site-core", action, str(root)],
        text=True,
        capture_output=True,
        check=False,
    )


def payload_snapshot(root: Path) -> dict[str, bytes]:
    result = {}
    for path in sorted((root / "payload").rglob("*")):
        if path.is_file():
            result[path.relative_to(root / "payload").as_posix()] = path.read_bytes()
    return result


def payload_fingerprint(root: Path) -> str:
    """Independent FNV-1a over sorted relative paths and file bytes."""
    value = 1469598103934665603
    for path in sorted((root / "payload").rglob("*")):
        if path.is_file():
            relative = path.relative_to(root / "payload").as_posix().encode()
            for byte in relative + path.read_bytes():
                value ^= byte
                value = (value * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return f"{value:016x}"


def read_account(root: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in (root / ".site/account").read_text().splitlines()
        if "=" in line
    )


def assert_serviceable(root: Path, before: dict[str, bytes]) -> None:
    account = read_account(root)
    assert (root / ".site/pending").read_text() == ""
    assert (root / ".site/ready").read_text() == "1\n"
    assert (root / ".site/status").read_text() == "published\n"
    assert account["count"] == str(len(before))
    assert account["fingerprint"] == payload_fingerprint(root)
    assert int(account["generation"]) >= 0
    assert payload_snapshot(root) == before


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def observed_text(root: Path) -> str:
    """Match site-core scan output for the live payload tree."""
    paths = sorted(
        path.relative_to(root / "payload").as_posix()
        for path in (root / "payload").rglob("*")
        if path.is_file()
    )
    lines = [
        f"count={len(paths)}",
        f"fingerprint={payload_fingerprint(root)}",
        *[f"path={path}" for path in paths],
        "",
    ]
    return "\n".join(lines)


def make_clean(root: Path) -> None:
    (root / ".site/pending").write_text("")
    if (root / "namespace/retired/link").exists():
        (root / "namespace/retired/link").unlink()
    write(
        root / ".site/account",
        "\n".join(
            [
                "count=2",
                f"fingerprint={payload_fingerprint(root)}",
                "generation=1",
                "",
            ]
        ),
    )
    write(root / ".site/observed", observed_text(root))
    (root / ".site/status").write_text("published\n")
    (root / ".site/ready").write_text("1\n")


def highest_matching_generation(root: Path) -> str:
    scan_fp = payload_fingerprint(root)
    count = str(len(payload_snapshot(root)))
    best = -1
    for name in ("slot-a", "slot-b"):
        path = root / ".site" / name
        if not path.exists():
            continue
        record = dict(
            line.split("=", 1) for line in path.read_text().splitlines() if "=" in line
        )
        if record.get("count") != count or record.get("fingerprint") != scan_fp:
            continue
        generation = int(record.get("generation", "-1"))
        best = max(best, generation)
    assert best >= 0
    return str(best)


def test_alpha(tmp_path: Path) -> None:
    """Manual entry completes deferred namespace work."""
    root = make_state(tmp_path)
    before = payload_snapshot(root)
    run(ADMIN, root)
    assert_serviceable(root, before)
    assert not (root / "namespace/retired/link").exists()


def test_beta(tmp_path: Path) -> None:
    """Stale accounting converges without payload loss."""
    root = make_state(tmp_path, pending="")
    before = payload_snapshot(root)
    run(ADMIN, root)
    assert_serviceable(root, before)


def test_gamma(tmp_path: Path) -> None:
    """Publication residue cannot stand in for serviceability."""
    root = make_state(tmp_path)
    write(root / ".site/ready", "1\n")
    before = payload_snapshot(root)
    run(ADMIN, root)
    assert_serviceable(root, before)
    assert not (root / "namespace/retired/link").exists()


def test_delta(tmp_path: Path) -> None:
    """An early interruption can be reconstructed."""
    root = make_state(tmp_path)
    (root / ".site/account").unlink()
    before = payload_snapshot(root)
    run(ADMIN, root)
    assert_serviceable(root, before)
    assert not (root / "namespace/retired/link").exists()


def test_epsilon(tmp_path: Path) -> None:
    """Competing durable candidates resolve to the newer matching generation."""
    root = make_state(tmp_path, pending="")
    fingerprint = payload_fingerprint(root)
    write(
        root / ".site" / "slot-a",
        "\n".join(
            [
                "count=2",
                f"fingerprint={fingerprint}",
                "generation=11",
                "",
            ]
        ),
    )
    write(
        root / ".site" / "slot-b",
        "\n".join(
            [
                "count=2",
                f"fingerprint={fingerprint}",
                "generation=4",
                "",
            ]
        ),
    )
    expected_generation = highest_matching_generation(root)
    before = payload_snapshot(root)
    run(ADMIN, root)
    assert_serviceable(root, before)
    assert read_account(root)["generation"] == expected_generation
    assert expected_generation == "11"


def test_zeta(tmp_path: Path) -> None:
    """Activation and manual entry converge identically."""
    manual = make_state(tmp_path / "layout-a")
    activation = make_state(tmp_path / "layout-b")
    manual_payload = payload_snapshot(manual)
    activation_payload = payload_snapshot(activation)
    run(ADMIN, manual)
    run(ACTIVATE, activation)
    assert_serviceable(manual, manual_payload)
    assert_serviceable(activation, activation_payload)
    assert snapshot(manual) == snapshot(activation)


def test_eta(tmp_path: Path) -> None:
    """Mixed deferred work preserves a larger payload tree."""
    root = make_state(tmp_path)
    write(root / "payload/archive/gamma.txt", "archived payload\n")
    write(root / "namespace/retired/second", "retired\n")
    write(root / ".site/pending", "drop:retired/link\ndrop:retired/second\n")
    before = payload_snapshot(root)
    run(ADMIN, root)
    assert_serviceable(root, before)
    assert not (root / "namespace/retired/link").exists()
    assert not (root / "namespace/retired/second").exists()


def test_theta(tmp_path: Path) -> None:
    """A successful repeat is byte-stable."""
    root = make_state(tmp_path)
    before = payload_snapshot(root)
    run(ADMIN, root)
    assert_serviceable(root, before)
    first = snapshot(root)
    run(ADMIN, root)
    assert snapshot(root) == first


def test_iota(tmp_path: Path) -> None:
    """Activation clears an incomplete publication state."""
    root = make_state(tmp_path)
    write(root / ".site/ready", "1\n")
    before = payload_snapshot(root)
    run(ACTIVATE, root)
    assert_serviceable(root, before)
    assert not (root / "namespace/retired/link").exists()


def test_kappa(tmp_path: Path) -> None:
    """An already clean target remains unchanged."""
    root = make_state(tmp_path)
    make_clean(root)
    before = snapshot(root)
    run(ADMIN, root)
    assert snapshot(root) == before


def test_lambda(tmp_path: Path) -> None:
    """Malformed durable work fails closed and remains inspectable."""
    root = make_state(tmp_path, pending="unknown-record\n")
    before_payload = payload_snapshot(root)
    result = run(ADMIN, root)
    assert result.returncode != 0
    assert (root / ".site/pending").read_text() == "unknown-record\n"
    assert payload_snapshot(root) == before_payload
    assert (root / ".site/ready").read_text() != "1\n"
    inspect = run_core("inspect", root)
    assert inspect.returncode == 0
    assert "state=serviceable" not in inspect.stdout
    assert "pending=yes" in inspect.stdout


def test_mu(tmp_path: Path) -> None:
    """An in-use target is refused without mutation."""
    root = make_state(tmp_path)
    write(root / ".site/busy", "1\n")
    before = snapshot(root)
    result = run(ADMIN, root)
    assert result.returncode != 0
    assert snapshot(root) == before


def test_nu(tmp_path: Path) -> None:
    """Payload content changes must change recorded accounting fingerprints."""
    root = make_state(tmp_path, pending="")
    first_before = payload_snapshot(root)
    run(ADMIN, root)
    assert_serviceable(root, first_before)
    first_fp = read_account(root)["fingerprint"]

    write(root / "payload/alpha.txt", "alpha payload mutated\n")
    write(root / ".site/status", "prepared\n")
    write(root / ".site/ready", "")
    write(root / ".site/account", "count=99\nfingerprint=stale\ngeneration=1\n")
    write(root / ".site/sequence", "3\n")
    second_before = payload_snapshot(root)
    expected = payload_fingerprint(root)
    assert expected != first_fp
    run(ADMIN, root)
    assert_serviceable(root, second_before)
    assert read_account(root)["fingerprint"] == expected
    assert read_account(root)["fingerprint"] != first_fp


def test_xi(tmp_path: Path) -> None:
    """site-core inspect/check report the same serviceable end state as admin."""
    root = make_state(tmp_path)
    before = payload_snapshot(root)
    run(ADMIN, root)
    assert_serviceable(root, before)
    inspect = run_core("inspect", root)
    assert inspect.returncode == 0
    assert "root=valid" in inspect.stdout
    assert "busy=no" in inspect.stdout
    assert "pending=no" in inspect.stdout
    assert "account=current" in inspect.stdout
    assert "state=serviceable" in inspect.stdout
    check = run_core("check", root)
    assert check.returncode == 0
    assert "state=serviceable" in check.stdout


def test_omicron(tmp_path: Path) -> None:
    """Lower-level commit and publish refuse while deferred work remains."""
    root = make_state(tmp_path)
    fingerprint = payload_fingerprint(root)
    write(
        root / ".site/account",
        "\n".join(
            [
                "count=2",
                f"fingerprint={fingerprint}",
                "generation=3",
                "",
            ]
        ),
    )
    before = snapshot(root)
    commit = run_core("commit", root)
    assert commit.returncode != 0
    publish = run_core("publish", root)
    assert publish.returncode != 0
    assert (root / ".site/pending").read_text() == "drop:retired/link\n"
    assert (root / ".site/ready").read_text() != "1\n"
    assert snapshot(root) == before
