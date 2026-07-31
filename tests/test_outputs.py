from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

import pytest

APP = Path("/app")
REBUILD = APP / "tools" / "rebuild-runtime"
RUN = APP / "tools" / "run-runtime"
ROLLBACK = APP / "tools" / "rollback-runtime"
ROUTES = ("settlement", "refund", "reconcile", "drain")
DECISIONS = {
    "settlement": "accept",
    "refund": "review",
    "reconcile": "hold",
    "drain": "quiesce",
}


def run(
    *args: str, check: bool = True, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        args, text=True, capture_output=True, check=check, env=merged, timeout=45
    )


def finish(process: subprocess.Popen[str], timeout: float = 30) -> tuple[str, str]:
    try:
        return process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        pytest.fail(
            f"process exceeded {timeout}s and was killed: stdout={stdout!r} stderr={stderr!r}"
        )


@pytest.fixture(scope="session")
def runtime_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("runtime-template") / "ledger root"
    run(str(REBUILD), str(root))
    return root


@pytest.fixture()
def runtime(tmp_path: Path, runtime_template: Path) -> Path:
    root = tmp_path / "ledger root"
    shutil.copytree(runtime_template, root, symlinks=True)
    return root


def active_release(root: Path) -> Path:
    link = root / "opt/ledger/current"
    assert link.is_symlink()
    return link.resolve(strict=True)


@contextmanager
def changed_refund_source():
    request = APP / "requests/refund.req"
    original = request.read_bytes()
    request.write_bytes(b"refund\r\n")
    try:
        yield
    finally:
        request.write_bytes(original)


def parse_fields(output: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for item in output.strip().split():
        key, value = item.split("=", 1)
        fields[key] = value
    return fields


def expected(mode: str, route: str) -> dict[str, str]:
    optimized = mode == "v3"
    decision = DECISIONS[route]
    return {
        "request": route,
        "plugin": "x86-64-v3" if optimized else "baseline",
        "rules": "vector" if optimized else "stable",
        "audit": "simd-journal" if optimized else "journal",
        "generation": "3" if optimized else "2",
        "abi": "LEDGER_2.1",
        "decision": f"vector-{decision}" if optimized else decision,
    }


def run_direct(
    root: Path, mode: str, route: str, *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    loader = "/lib64/ld-linux-x86-64.so.2"
    app = "/opt/ledger/current/bin/ledger-gateway"
    request = f"/opt/ledger/current/requests/{route}.req"
    if mode == "baseline":
        args = ["chroot", str(root), loader, "--glibc-hwcaps-mask", "", app, request]
    else:
        args = [
            "chroot",
            str(root),
            loader,
            "--inhibit-cache",
            "--library-path",
            "/opt/ledger/current/lib",
            "--glibc-hwcaps-prepend",
            "x86-64-v3",
            app,
            request,
        ]
    return run(*args, check=check, env={"LD_LIBRARY_PATH": "/poison"})


def test_route_matrix_selects_one_matching_native_stack(runtime: Path) -> None:
    for mode in ("baseline", "v3"):
        for route in ROUTES:
            result = run(
                str(RUN),
                str(runtime),
                mode,
                route,
                env={"LD_LIBRARY_PATH": "/does/not/exist"},
            )
            assert parse_fields(result.stdout) == expected(mode, route)


def test_direct_loader_matches_wrapper_for_both_generations(runtime: Path) -> None:
    for mode in ("baseline", "v3"):
        assert parse_fields(run_direct(runtime, mode, "refund").stdout) == expected(
            mode, "refund"
        )


def test_cache_absence_and_regeneration_do_not_change_selection(runtime: Path) -> None:
    cache = runtime / "etc/ld.so.cache"
    cache.unlink()
    for mode in ("baseline", "v3"):
        assert parse_fields(
            run(str(RUN), str(runtime), mode, "settlement").stdout
        ) == expected(mode, "settlement")
    run("ldconfig", "-r", str(runtime))
    for mode in ("baseline", "v3"):
        assert parse_fields(
            run(str(RUN), str(runtime), mode, "reconcile").stdout
        ) == expected(mode, "reconcile")
    assert (
        runtime / "etc/ld.so.conf.d/ledger-gateway.conf"
    ).read_text().strip() == "/opt/ledger/current/lib"


def test_release_manifest_and_identity_cover_exact_payload(runtime: Path) -> None:
    release = active_release(runtime)
    manifest = release / "release.manifest"
    release_id = (release / "release.id").read_text().strip()
    assert release_id == hashlib.sha256(manifest.read_bytes()).hexdigest()
    rows = [line.split(maxsplit=1) for line in manifest.read_text().splitlines()]
    paths = [row[1] for row in rows]
    assert paths == sorted(paths)
    actual = sorted(
        str(path.relative_to(release))
        for top in ("bin", "lib", "requests")
        for path in (release / top).rglob("*")
        if path.is_file() and not path.is_symlink()
    )
    assert paths == actual
    assert all(
        hashlib.sha256((release / path).read_bytes()).hexdigest() == digest
        for digest, path in rows
    )
    assert release.name == f"ledger-gateway-2026.07-{release_id}"
    assert not (runtime / "opt/ledger/previous").exists()


def provenance_records(runtime: Path) -> tuple[Path, list[str], list[list[str]]]:
    release = active_release(runtime)
    provenance = release / "release.provenance"
    records = provenance.read_text().splitlines()
    return release, records, [line.split() for line in records[1:]]


def test_provenance_names_abi_and_every_native_build(runtime: Path) -> None:
    release, records, elf_records = provenance_records(runtime)
    assert records[0] == "abi LEDGER_2.1"
    native_files = sorted(
        str(path.relative_to(release))
        for top in ("bin", "lib")
        for path in (release / top).rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and path.read_bytes()[:4] == b"\x7fELF"
    )
    assert [row[1] for row in elf_records] == native_files
    assert len(elf_records) == 7


def test_provenance_build_ids_match_the_signed_elf_files(runtime: Path) -> None:
    release, _records, elf_records = provenance_records(runtime)
    for marker, path, build_id in elf_records:
        assert marker == "elf"
        assert len(build_id) >= 32 and set(build_id) <= set("0123456789abcdef")
        assert (
            f"Build ID: {build_id}" in run("readelf", "-n", str(release / path)).stdout
        )


def test_attestation_and_signature_bind_release_abi_and_provenance(
    runtime: Path,
) -> None:
    release = active_release(runtime)
    provenance = release / "release.provenance"
    release_id = (release / "release.id").read_text().strip()
    provenance_hash = hashlib.sha256(provenance.read_bytes()).hexdigest()
    assert (release / "release.attestation").read_text() == (
        f"release_id={release_id}\nabi=LEDGER_2.1\nprovenance_sha256={provenance_hash}\n"
    )
    verified = run(
        "openssl",
        "pkeyutl",
        "-verify",
        "-pubin",
        "-inkey",
        str(APP / "packaging/release-signing.pub"),
        "-rawin",
        "-in",
        str(release / "release.attestation"),
        "-sigfile",
        str(release / "release.signature"),
    )
    assert verified.returncode == 0


@pytest.mark.parametrize("corruption", ["request", "library", "extra"])
def test_active_release_tampering_fails_closed(runtime: Path, corruption: str) -> None:
    release = active_release(runtime)
    if corruption == "request":
        (release / "requests/refund.req").write_text("settlement\n", encoding="utf-8")
    elif corruption == "library":
        with (release / "lib/libledger_rules.so.1.0").open("ab") as handle:
            handle.write(b"tamper")
    else:
        (release / "lib/untracked.so").write_bytes(b"extra")
    result = run(str(RUN), str(runtime), "baseline", "refund", check=False)
    assert result.returncode != 0
    if corruption == "request":
        diagnostic = result.stderr.lower()
        assert any(
            word in diagnostic
            for word in ("integrity", "checksum", "manifest", "payload", "trust")
        )


def test_recomputed_manifest_without_trusted_signature_is_rejected(
    runtime: Path,
) -> None:
    release = active_release(runtime)
    request = release / "requests/refund.req"
    request.write_bytes(b"refund\r\n")
    manifest = release / "release.manifest"
    rows = []
    for line in manifest.read_text().splitlines():
        digest, path = line.split(maxsplit=1)
        if path == "requests/refund.req":
            digest = hashlib.sha256(request.read_bytes()).hexdigest()
        rows.append(f"{digest}  {path}")
    manifest.write_text("\n".join(rows) + "\n")
    forged_id = hashlib.sha256(manifest.read_bytes()).hexdigest()
    (release / "release.id").write_text(forged_id + "\n")
    provenance_hash = hashlib.sha256(
        (release / "release.provenance").read_bytes()
    ).hexdigest()
    (release / "release.attestation").write_text(
        f"release_id={forged_id}\nabi=LEDGER_2.1\nprovenance_sha256={provenance_hash}\n"
    )
    result = run(str(RUN), str(runtime), "baseline", "refund", check=False)
    assert result.returncode != 0
    assert "signature" in result.stderr.lower()


def test_mixed_hwcaps_dependency_generation_is_rejected_natively(runtime: Path) -> None:
    release = active_release(runtime)
    audit_link = release / "lib/glibc-hwcaps/x86-64-v3/libledger_audit.so.1"
    audit_link.unlink()
    audit_link.symlink_to("../../libledger_audit.so.1.0")
    result = run_direct(runtime, "v3", "settlement", check=False)
    assert result.returncode != 0
    assert "policy load failed" in result.stderr or "mixed generations" in result.stderr


def test_failed_candidate_never_changes_active_release(runtime: Path) -> None:
    before_link = os.readlink(runtime / "opt/ledger/current")
    before_id = (active_release(runtime) / "release.id").read_text()
    failed = run(
        str(REBUILD),
        str(runtime),
        check=False,
        env={"LEDGER_REBUILD_FAIL": "before-promote"},
    )
    assert failed.returncode != 0
    assert os.readlink(runtime / "opt/ledger/current") == before_link
    assert (active_release(runtime) / "release.id").read_text() == before_id
    assert parse_fields(
        run(str(RUN), str(runtime), "baseline", "settlement").stdout
    ) == expected("baseline", "settlement")


def test_next_successful_refresh_removes_abandoned_candidates(runtime: Path) -> None:
    failed = run(
        str(REBUILD),
        str(runtime),
        check=False,
        env={"LEDGER_REBUILD_FAIL": "before-promote"},
    )
    assert failed.returncode != 0
    run(str(REBUILD), str(runtime))
    assert not list((runtime / "opt/ledger/releases").glob(".candidate.*"))


def test_refresh_repairs_a_stale_active_tree_in_its_content_slot(runtime: Path) -> None:
    old_release = active_release(runtime)
    stale = old_release / "lib/glibc-hwcaps/x86-64-v3/stale-service.so"
    stale.write_bytes(b"stale")
    run(str(REBUILD), str(runtime))
    assert active_release(runtime) == old_release
    assert not (
        active_release(runtime) / "lib/glibc-hwcaps/x86-64-v3/stale-service.so"
    ).exists()
    assert parse_fields(run(str(RUN), str(runtime), "v3", "refund").stdout) == expected(
        "v3", "refund"
    )


def test_stale_tree_repair_does_not_create_false_rollback_history(
    runtime: Path,
) -> None:
    (
        active_release(runtime) / "lib/glibc-hwcaps/x86-64-v3/stale-service.so"
    ).write_bytes(b"stale")
    run(str(REBUILD), str(runtime))
    assert not (runtime / "opt/ledger/previous").exists()


def test_verified_rollback_recovers_from_damaged_current(runtime: Path) -> None:
    with changed_refund_source():
        run(str(REBUILD), str(runtime))
    healthy_previous = (runtime / "opt/ledger/previous").resolve()
    with (active_release(runtime) / "lib/libledger_policy.so.2.0").open("ab") as handle:
        handle.write(b"damage")
    assert (
        run(str(RUN), str(runtime), "baseline", "settlement", check=False).returncode
        != 0
    )
    run(str(ROLLBACK), str(runtime))
    assert active_release(runtime) == healthy_previous
    assert parse_fields(
        run(str(RUN), str(runtime), "baseline", "settlement").stdout
    ) == expected("baseline", "settlement")
    assert parse_fields(
        run(str(RUN), str(runtime), "v3", "settlement").stdout
    ) == expected("v3", "settlement")


def test_concurrent_refreshes_serialize_and_leave_no_candidates(runtime: Path) -> None:
    before = os.readlink(runtime / "opt/ledger/current")
    first = subprocess.Popen(
        [str(REBUILD), str(runtime)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    second = subprocess.Popen(
        [str(REBUILD), str(runtime)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    first_out, first_err = finish(first)
    second_out, second_err = finish(second)
    assert (first.returncode, second.returncode) == (0, 0), (
        first_out,
        first_err,
        second_out,
        second_err,
    )
    assert not list((runtime / "opt/ledger/releases").glob(".candidate.*"))
    assert os.readlink(runtime / "opt/ledger/current") == before
    assert not (runtime / "opt/ledger/previous").exists()
    assert parse_fields(
        run(str(RUN), str(runtime), "v3", "reconcile").stdout
    ) == expected("v3", "reconcile")


def test_identical_refresh_is_a_content_addressed_noop(runtime: Path) -> None:
    current = os.readlink(runtime / "opt/ledger/current")
    release_dirs = sorted((runtime / "opt/ledger/releases").iterdir())
    run(str(REBUILD), str(runtime))
    assert os.readlink(runtime / "opt/ledger/current") == current
    assert sorted((runtime / "opt/ledger/releases").iterdir()) == release_dirs
    assert not (runtime / "opt/ledger/previous").exists()


def test_after_current_fault_keeps_new_current_runnable_and_records_recovery(
    runtime: Path,
) -> None:
    old_target = os.readlink(runtime / "opt/ledger/current")
    with changed_refund_source():
        failed = run(
            str(REBUILD),
            str(runtime),
            check=False,
            env={"LEDGER_REBUILD_FAIL": "after-current"},
        )
        assert failed.returncode != 0
        new_target = os.readlink(runtime / "opt/ledger/current")
        assert new_target != old_target
        pending = runtime / "var/lib/ledger/activation.pending"
        assert pending.is_file()
        assert parse_fields(
            run(str(RUN), str(runtime), "v3", "refund").stdout
        ) == expected("v3", "refund")


def test_next_refresh_completes_an_after_current_activation(runtime: Path) -> None:
    old_target = os.readlink(runtime / "opt/ledger/current")
    with changed_refund_source():
        failed = run(
            str(REBUILD),
            str(runtime),
            check=False,
            env={"LEDGER_REBUILD_FAIL": "after-current"},
        )
        assert failed.returncode != 0
        new_target = os.readlink(runtime / "opt/ledger/current")
        pending = runtime / "var/lib/ledger/activation.pending"
        run(str(REBUILD), str(runtime))
        assert not pending.exists()
        assert os.readlink(runtime / "opt/ledger/current") == new_target
        assert os.readlink(runtime / "opt/ledger/previous") == old_target


def test_drain_reader_keeps_its_release_while_refresh_waits(runtime: Path) -> None:
    old_target = os.readlink(runtime / "opt/ledger/current")
    with changed_refund_source():
        reader = subprocess.Popen(
            [str(RUN), str(runtime), "baseline", "drain"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(0.5)
        refresh = subprocess.Popen(
            [str(REBUILD), str(runtime)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(2.2)
        assert reader.poll() is None
        assert refresh.poll() is None
        assert os.readlink(runtime / "opt/ledger/current") == old_target
        reader_out, reader_err = finish(reader, timeout=10)
        assert reader.returncode == 0, reader_err
        assert parse_fields(reader_out) == expected("baseline", "drain")
        refresh_out, refresh_err = finish(refresh)
        assert refresh.returncode == 0, (refresh_out, refresh_err)
        assert os.readlink(runtime / "opt/ledger/current") != old_target


def test_elf_dependencies_sonames_versions_and_origin_runpath(runtime: Path) -> None:
    release = active_release(runtime)
    base_policy = release / "lib/libledger_policy.so.2.0"
    v3_policy = release / "lib/glibc-hwcaps/x86-64-v3/libledger_policy.so.2.1"
    for policy in (base_policy, v3_policy):
        dynamic = run("readelf", "-d", str(policy)).stdout
        assert "Shared library: [libledger_rules.so.1]" in dynamic
        assert "Shared library: [libledger_audit.so.1]" in dynamic
        assert "Library soname: [libledger_policy.so.2]" in dynamic
        assert "Library runpath: [$ORIGIN]" in dynamic
    assert (
        "LEDGER_RULES_1.0"
        in run(
            "readelf", "--version-info", str(release / "lib/libledger_rules.so.1.0")
        ).stdout
    )
    assert (
        "LEDGER_RULES_2.0"
        in run(
            "readelf",
            "--version-info",
            str(release / "lib/glibc-hwcaps/x86-64-v3/libledger_rules.so.1.1"),
        ).stdout
    )
    assert (
        "LEDGER_AUDIT_1.0"
        in run(
            "readelf", "--version-info", str(release / "lib/libledger_audit.so.1.0")
        ).stdout
    )
    assert (
        "LEDGER_AUDIT_2.0"
        in run(
            "readelf",
            "--version-info",
            str(release / "lib/glibc-hwcaps/x86-64-v3/libledger_audit.so.1.1"),
        ).stdout
    )
    for policy in (base_policy, v3_policy):
        assert (
            "LEDGER_POLICY_2.1" in run("readelf", "--version-info", str(policy)).stdout
        )
    gateway_symbols = run("objdump", "-T", str(release / "bin/ledger-gateway")).stdout
    assert "dlvsym" in gateway_symbols


def test_release_permissions_and_links_are_safe(runtime: Path) -> None:
    release = active_release(runtime)
    assert not os.path.isabs(os.readlink(runtime / "opt/ledger/current"))
    for path in release.rglob("*"):
        if path.is_symlink():
            assert not os.path.isabs(os.readlink(path))
        elif path.is_file():
            assert not (stat.S_IMODE(path.stat().st_mode) & 0o022)
    assert os.access(release / "bin/ledger-gateway", os.X_OK)
    assert (release / "bin/ledger-gateway").read_bytes()[:4] == b"\x7fELF"


def test_invalid_run_and_root_interfaces_fail_without_damage(runtime: Path) -> None:
    current = os.readlink(runtime / "opt/ledger/current")
    cases = [
        (str(RUN), str(runtime), "avx", "settlement"),
        (str(RUN), str(runtime), "baseline", "../settlement"),
        (str(REBUILD), "relative-root"),
        (str(REBUILD), "/"),
        (str(REBUILD), f"{runtime.parent}/./{runtime.name}"),
    ]
    for args in cases:
        assert run(*args, check=False).returncode != 0
    assert os.readlink(runtime / "opt/ledger/current") == current


def test_missing_rollback_fails_without_changing_current(runtime: Path) -> None:
    current = os.readlink(runtime / "opt/ledger/current")
    assert run(str(ROLLBACK), str(runtime), check=False).returncode != 0
    assert os.readlink(runtime / "opt/ledger/current") == current


def test_symlinked_root_is_rejected(runtime: Path, tmp_path: Path) -> None:
    alias = tmp_path / "runtime-alias"
    alias.symlink_to(runtime, target_is_directory=True)
    assert run(str(REBUILD), str(alias), check=False).returncode != 0


def test_active_link_escape_is_rejected(runtime: Path) -> None:
    current = runtime / "opt/ledger/current"
    current.unlink()
    current.symlink_to("../../../../tmp")
    result = run(str(RUN), str(runtime), "baseline", "settlement", check=False)
    assert result.returncode != 0
    assert any(
        word in result.stderr.lower()
        for word in ("integrity", "unsafe", "escape", "release")
    )
