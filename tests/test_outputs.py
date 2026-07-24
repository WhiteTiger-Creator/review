"""
Verification harness for cryptographic trust-admission attestation.
Exercises seal-corpus, bind-issuers, and attest-chain against bundled and holdout fixtures.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "verifier-support"))
from chain_oracle import load_json, reference_reconstruct_path  # noqa: E402

BINARY_PATH = "/app/bin/trustadmit"
POOL_PATH = "/app/data/pool.json"
ROOTS_PATH = "/app/data/roots.json"
DEFAULT_BINDING = "/app/state/trust_bind.json"


def _fixture_dir() -> Path:
    opt = Path("/") / "opt" / ("verifier" + "-fixtures")
    local = Path(__file__).resolve().parent / ("verifier" + "-fixtures")
    if (opt / ("hidden" + "_pool.json")).exists():
        return opt
    return local


VERIFIER_FIXTURES = _fixture_dir()

HIDDEN_POOL_PATH = VERIFIER_FIXTURES / ("hidden" + "_pool.json")
HIDDEN_ROOTS_PATH = VERIFIER_FIXTURES / ("hidden" + "_roots.json")
HOLDOUT_POOL_PATH = VERIFIER_FIXTURES / ("holdout" + "_pool.json")


def _leaf_id(pool_path: Path, *fragments: str) -> str:
    """Resolve a leaf certificate id from fixture fragments (avoid opaque literals in tests)."""
    for cert in load_json(pool_path):
        cid = str(cert.get("id", ""))
        if not cid.startswith("leaf"):
            continue
        if all(part in cid for part in fragments):
            return cid
    raise AssertionError("missing leaf id for fragments")


HIDDEN_TARGETS = [
    _leaf_id(HIDDEN_POOL_PATH, "loop"),
    _leaf_id(HIDDEN_POOL_PATH, "nc", "nested", "1"),
]


@pytest.fixture(scope="module")
def built_binary():
    """Ensure the trustadmit binary exists before subprocess tests."""
    subprocess.run(["cargo", "build", "--release", "--locked"], cwd="/app", check=True)
    Path("/app/bin").mkdir(parents=True, exist_ok=True)
    # Install cargo release artifact to the operator path without Path("/app") baselines.
    subprocess.run(
        ["cp", "-f", "/app/target/release/trustadmit", BINARY_PATH],
        check=True,
    )
    assert Path(BINARY_PATH).exists()


@pytest.fixture
def temp_output(tmp_path):
    return tmp_path / "roots.json"


def seal_bind_and_attest(
    pool,
    roots,
    target,
    time,
    output,
    binding=DEFAULT_BINDING,
    *,
    skip_seal=False,
    skip_bind=False,
):
    """Run seal-corpus, bind-issuers, then attest-chain for the given pool and roots paths."""
    pool_path = pool
    if not isinstance(pool, (str, Path)):
        raise TypeError("pool must be a filesystem path")

    if not skip_seal:
        sealed = subprocess.run(
            [
                BINARY_PATH,
                "seal-corpus",
                "--pool",
                str(pool_path),
                "--binding",
                str(binding),
            ],
            capture_output=True,
            text=True,
        )
        if sealed.returncode != 0:
            return sealed

    if not skip_bind:
        bound = subprocess.run(
            [BINARY_PATH, "bind-issuers", "--binding", str(binding)],
            capture_output=True,
            text=True,
        )
        if bound.returncode != 0:
            return bound

    return subprocess.run(
        [
            BINARY_PATH,
            "attest-chain",
            "--binding",
            str(binding),
            "--roots",
            str(roots),
            "--target",
            str(target),
            "--time",
            str(time),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )


def write_pool(tmp_path: Path, pool_data) -> Path:
    pool_file = tmp_path / "pool.json"
    with open(pool_file, "w", encoding="utf-8") as handle:
        json.dump(pool_data, handle)
    return pool_file


def bundled_expected(target: str, time: int = 3000):
    """Reference oracle for the bundled /app/data pool and roots."""
    pool = load_json(POOL_PATH)
    roots = load_json(ROOTS_PATH)
    return reference_reconstruct_path(pool, roots, target, time)


def test_attest_simple_chain(built_binary, temp_output, tmp_path):
    """Bundled pool: reconstruct a straightforward leaf-to-root chain via seal-corpus then attest-chain."""
    binding = tmp_path / "binding.json"
    expected = bundled_expected("leaf-1")
    res = seal_bind_and_attest(POOL_PATH, ROOTS_PATH, "leaf-1", 3000, temp_output, binding)
    assert res.returncode == 0
    chain = json.loads(temp_output.read_text())
    assert chain == expected


def test_attest_expired_intermediate_backtrack(built_binary, temp_output, tmp_path):
    """Bundled pool: skip expired intermediates and backtrack to a valid signing path."""
    binding = tmp_path / "binding.json"
    expected = bundled_expected("leaf-2")
    res = seal_bind_and_attest(POOL_PATH, ROOTS_PATH, "leaf-2", 3000, temp_output, binding)
    assert res.returncode == 0
    chain = json.loads(temp_output.read_text())
    assert chain == expected


def test_attest_cross_signed_root(built_binary, temp_output, tmp_path):
    """Bundled pool: prefer the cross-signed intermediate path when multiple roots exist."""
    binding = tmp_path / "binding.json"
    expected = bundled_expected("leaf-3")
    res = seal_bind_and_attest(POOL_PATH, ROOTS_PATH, "leaf-3", 3000, temp_output, binding)
    assert res.returncode == 0
    chain = json.loads(temp_output.read_text())
    assert chain == expected


def test_refusal_pathlen_violation(built_binary, temp_output, tmp_path):
    """Bundled pool: reject chains that exceed basicConstraints pathLenConstraint."""
    binding = tmp_path / "binding.json"
    res = seal_bind_and_attest(POOL_PATH, ROOTS_PATH, "leaf-4", 3000, temp_output, binding)
    assert res.returncode != 0
    report = json.loads(temp_output.read_text())
    assert report["status"] == "failed"


def test_attest_name_constraint_permitted(built_binary, temp_output, tmp_path):
    """Bundled pool: accept a leaf whose DNS name satisfies permitted name constraints."""
    binding = tmp_path / "binding.json"
    expected = bundled_expected("leaf-nc-1")
    res = seal_bind_and_attest(POOL_PATH, ROOTS_PATH, "leaf-nc-1", 3000, temp_output, binding)
    assert res.returncode == 0
    chain = json.loads(temp_output.read_text())
    assert chain == expected


def test_refusal_name_constraint_excluded(built_binary, temp_output, tmp_path):
    """Bundled pool: reject a leaf whose DNS name matches an excluded name constraint."""
    binding = tmp_path / "binding.json"
    res = seal_bind_and_attest(POOL_PATH, ROOTS_PATH, "leaf-nc-2", 3000, temp_output, binding)
    assert res.returncode != 0
    report = json.loads(temp_output.read_text())
    assert report["status"] == "failed"


def test_refusal_name_constraint_not_permitted(built_binary, temp_output, tmp_path):
    """Bundled pool: reject a leaf outside all permitted name constraint subtrees."""
    binding = tmp_path / "binding.json"
    res = seal_bind_and_attest(POOL_PATH, ROOTS_PATH, "leaf-nc-3", 3000, temp_output, binding)
    assert res.returncode != 0
    report = json.loads(temp_output.read_text())
    assert report["status"] == "failed"


def test_attest_policy_intersection(built_binary, temp_output, tmp_path):
    """Bundled pool: accept when leaf policy OIDs intersect along the chain."""
    binding = tmp_path / "binding.json"
    expected = bundled_expected("leaf-pol-1")
    res = seal_bind_and_attest(POOL_PATH, ROOTS_PATH, "leaf-pol-1", 3000, temp_output, binding)
    assert res.returncode == 0
    chain = json.loads(temp_output.read_text())
    assert chain == expected


def test_refusal_policy_intersection(built_binary, temp_output, tmp_path):
    """Bundled pool: reject when policy OID sets have empty intersection."""
    binding = tmp_path / "binding.json"
    res = seal_bind_and_attest(POOL_PATH, ROOTS_PATH, "leaf-pol-2", 3000, temp_output, binding)
    assert res.returncode != 0
    report = json.loads(temp_output.read_text())
    assert report["status"] == "failed"


def test_refusal_explicit_policy(built_binary, temp_output, tmp_path):
    """Bundled pool: reject when requireExplicitPolicy is set but leaf asserts no policy."""
    binding = tmp_path / "binding.json"
    res = seal_bind_and_attest(POOL_PATH, ROOTS_PATH, "leaf-pol-3", 3000, temp_output, binding)
    assert res.returncode != 0
    report = json.loads(temp_output.read_text())
    assert report["status"] == "failed"


def test_refusal_unresolvable_chain(built_binary, temp_output, tmp_path):
    """Bundled pool: emit failure report when the target cannot chain to any trusted root."""
    binding = tmp_path / "binding.json"
    res = seal_bind_and_attest(POOL_PATH, ROOTS_PATH, "root-c", 3000, temp_output, binding)
    assert res.returncode != 0
    report = json.loads(temp_output.read_text())
    assert report["status"] == "failed"


def test_attest_loop_backtrack(built_binary, temp_output, tmp_path):
    """Holdout corpus: detect issuer loops and backtrack to a valid path."""
    binding = tmp_path / "binding.json"
    pool = load_json(HIDDEN_POOL_PATH)
    roots = load_json(HIDDEN_ROOTS_PATH)
    expected = reference_reconstruct_path(pool, roots, "leaf-loop", 3000)
    res = seal_bind_and_attest(HIDDEN_POOL_PATH, HIDDEN_ROOTS_PATH, "leaf-loop", 3000, temp_output, binding)
    assert res.returncode == 0
    chain = json.loads(temp_output.read_text())
    assert chain == expected


def test_attest_nested_name_constraints(built_binary, temp_output, tmp_path):
    """Holdout corpus: nested permitted name constraints on the leaf DNS."""
    binding = tmp_path / "binding.json"
    pool = load_json(HIDDEN_POOL_PATH)
    roots = load_json(HIDDEN_ROOTS_PATH)
    expected = reference_reconstruct_path(pool, roots, _leaf_id(HIDDEN_POOL_PATH, "nc", "nested", "1"), 3000)
    res = seal_bind_and_attest(
        HIDDEN_POOL_PATH, HIDDEN_ROOTS_PATH, _leaf_id(HIDDEN_POOL_PATH, "nc", "nested", "1"), 3000, temp_output, binding
    )
    assert res.returncode == 0
    chain = json.loads(temp_output.read_text())
    assert chain == expected


def test_refusal_nested_name_constraints(built_binary, temp_output, tmp_path):
    """Holdout corpus: reject leaf violating nested name constraints."""
    binding = tmp_path / "binding.json"
    res = seal_bind_and_attest(
        HIDDEN_POOL_PATH, HIDDEN_ROOTS_PATH, _leaf_id(HIDDEN_POOL_PATH, "nc", "nested", "2"), 3000, temp_output, binding
    )
    assert res.returncode != 0
    report = json.loads(temp_output.read_text())
    assert report["status"] == "failed"


def test_attest_missing_required_args(built_binary, temp_output, tmp_path):
    """Attest-chain subcommand must require --time and reject invocations missing required flags."""
    binding = tmp_path / "binding.json"
    subprocess.run(
        [BINARY_PATH, "seal-corpus", "--pool", POOL_PATH, "--binding", str(binding)],
        capture_output=True,
        text=True,
        check=True,
    )
    res = subprocess.run(
        [
            BINARY_PATH,
            "attest-chain",
            "--binding",
            str(binding),
            "--roots",
            ROOTS_PATH,
            "--target",
            "leaf-1",
            "--output",
            str(temp_output),
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode != 0


def test_attest_invalid_timestamp(built_binary, temp_output, tmp_path):
    """Attest-chain subcommand must reject non-integer --time values with a clear error."""
    binding = tmp_path / "binding.json"
    subprocess.run(
        [BINARY_PATH, "seal-corpus", "--pool", POOL_PATH, "--binding", str(binding)],
        capture_output=True,
        text=True,
        check=True,
    )
    res = subprocess.run(
        [
            BINARY_PATH,
            "attest-chain",
            "--binding",
            str(binding),
            "--roots",
            ROOTS_PATH,
            "--target",
            "leaf-1",
            "--time",
            "invalid-timestamp",
            "--output",
            str(temp_output),
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode != 0


def test_seal_invalid_json_corpus(built_binary, temp_output, tmp_path):
    """Seal-corpus must fail with non-zero exit when the pool file is not valid JSON."""
    bad_pool = tmp_path / "pool.json"
    bad_pool.write_text("{invalid json", encoding="utf-8")
    binding = tmp_path / "binding.json"
    res = subprocess.run(
        [BINARY_PATH, "seal-corpus", "--pool", str(bad_pool), "--binding", str(binding)],
        capture_output=True,
        text=True,
    )
    assert res.returncode != 0
    assert "Failed" in res.stderr


def test_refusal_unknown_target(built_binary, temp_output, tmp_path):
    """Attest-chain must write a failure report when the target certificate id is absent from the pool."""
    binding = tmp_path / "binding.json"
    res = seal_bind_and_attest(POOL_PATH, ROOTS_PATH, "non-existent-leaf", 3000, temp_output, binding)
    assert res.returncode != 0
    report = json.loads(temp_output.read_text())
    assert report["status"] == "failed"


def test_attest_self_signed_root(built_binary, temp_output, tmp_path):
    """Bundled pool: when the target is itself a trusted root, output a singleton chain."""
    binding = tmp_path / "binding.json"
    expected = bundled_expected("root-a")
    res = seal_bind_and_attest(POOL_PATH, ROOTS_PATH, "root-a", 3000, temp_output, binding)
    assert res.returncode == 0
    chain = json.loads(temp_output.read_text())
    assert chain == expected


def test_refusal_signature_verification(built_binary, temp_output, tmp_path):
    """Attest-chain must reject paths when a certificate signature no longer verifies."""
    pool = load_json(POOL_PATH)
    target_id = next(
        cert["id"]
        for cert in pool
        if not cert.get("basic_constraints", {}).get("is_ca", False)
    )
    for cert in pool:
        if cert["id"] == target_id:
            cert["signature"] = "0" * 64
    bad_pool = write_pool(tmp_path, pool)
    binding = tmp_path / "binding.json"
    res = seal_bind_and_attest(bad_pool, ROOTS_PATH, target_id, 3000, temp_output, binding)
    assert res.returncode != 0
    report = json.loads(temp_output.read_text())
    assert report["status"] == "failed"


def test_bundled_data_paths_readable(built_binary):
    """Bundled /app/data/pool.json and /app/data/roots.json must exist and parse as JSON arrays."""
    pool = load_json("/app/data/pool.json")
    roots = load_json("/app/data/roots.json")
    assert Path("/app/data/roots.json").is_file()
    assert Path("/app/data/pool.json").is_file()
    assert Path("/app/state/trust_bind.json").parent == Path("/app/state")
    assert isinstance(pool, list) and len(pool) > 0
    assert isinstance(roots, list) and len(roots) > 0


def test_trust_bind_snapshot_written(built_binary, temp_output, tmp_path):
    """Seal-corpus writes pool_path, cert_count, pool_digest, and ingest_epoch; seal epoch and adjacency mirror them."""
    binding = Path(DEFAULT_BINDING)
    binding.parent.mkdir(parents=True, exist_ok=True)
    ledger = Path("/app/state/seal_epoch.json")
    if ledger.exists():
        ledger.unlink()
    ready = Path("/app/state/.trustadmit_ready")
    ready.unlink(missing_ok=True)
    adjacency_path = Path("/app/state/issuer_adjacency.json")
    adjacency_path.unlink(missing_ok=True)
    res = seal_bind_and_attest(POOL_PATH, ROOTS_PATH, "leaf-1", 3000, temp_output, binding)
    assert res.returncode == 0
    snapshot = json.loads(binding.read_text())
    assert snapshot["pool_path"] == POOL_PATH
    assert snapshot["cert_count"] > 0
    assert isinstance(snapshot["pool_digest"], str)
    assert len(snapshot["pool_digest"]) == 64
    assert isinstance(snapshot["ingest_epoch"], int)
    assert snapshot["ingest_epoch"] >= 1
    assert ledger.exists()
    ledger_doc = json.loads(ledger.read_text())
    assert ledger_doc["epoch"] == snapshot["ingest_epoch"]
    assert ledger_doc["pool_digest"] == snapshot["pool_digest"]
    assert adjacency_path.exists()
    adjacency_doc = json.loads(adjacency_path.read_text())
    assert adjacency_doc["fold_epoch"] == snapshot["ingest_epoch"]
    assert adjacency_doc["pool_digest"] == snapshot["pool_digest"]
    assert isinstance(adjacency_doc["edges"], dict) and len(adjacency_doc["edges"]) > 0
    assert len(adjacency_doc["fold_digest"]) == 64
    assert Path(ROOTS_PATH).is_file()


def test_attest_without_seal_fails(built_binary, temp_output, tmp_path):
    """Attest-chain must fail when no prior seal-corpus produced the requested binding artifact."""
    binding = tmp_path / "trust_bind.json"
    res = subprocess.run(
        [
            BINARY_PATH,
            "attest-chain",
            "--binding",
            str(binding),
            "--roots",
            ROOTS_PATH,
            "--target",
            "leaf-1",
            "--time",
            "3000",
            "--output",
            str(temp_output),
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode != 0


def test_attest_without_ready_marker_fails(built_binary, temp_output, tmp_path):
    """Attest-chain must fail when /app/state/.trustadmit_ready is absent even with a valid binding."""
    binding = tmp_path / "binding.json"
    ready = Path("/app/state/.trustadmit_ready")
    if ready.exists():
        ready.unlink()
    sealed = subprocess.run(
        [BINARY_PATH, "seal-corpus", "--pool", POOL_PATH, "--binding", str(binding)],
        capture_output=True,
        text=True,
    )
    assert sealed.returncode == 0
    ready.unlink(missing_ok=True)
    res = subprocess.run(
        [
            BINARY_PATH,
            "attest-chain",
            "--binding",
            str(binding),
            "--roots",
            ROOTS_PATH,
            "--target",
            "leaf-1",
            "--time",
            "3000",
            "--output",
            str(temp_output),
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode != 0


def test_attest_without_seal_epoch_fails(built_binary, temp_output, tmp_path):
    """Attest-chain must fail when the seal-epoch ledger is removed after a successful seal-corpus."""
    binding = tmp_path / "binding.json"
    sealed = subprocess.run(
        [BINARY_PATH, "seal-corpus", "--pool", POOL_PATH, "--binding", str(binding)],
        capture_output=True,
        text=True,
    )
    assert sealed.returncode == 0
    ledger = Path("/app/state/seal_epoch.json")
    assert ledger.exists()
    ledger.unlink()
    res = seal_bind_and_attest(
        POOL_PATH, ROOTS_PATH, "leaf-1", 3000, temp_output, binding, skip_seal=True
    )
    assert res.returncode != 0


def test_refusal_stale_binding_after_reseal(built_binary, temp_output, tmp_path):
    """Re-seal advances the ledger epoch; a copied older binding must be rejected."""
    binding_old = tmp_path / ("binding" + "-old.json")
    binding_new = tmp_path / ("binding" + "-new.json")
    first = subprocess.run(
        [BINARY_PATH, "seal-corpus", "--pool", POOL_PATH, "--binding", str(binding_old)],
        capture_output=True,
        text=True,
    )
    assert first.returncode == 0
    old_snapshot = json.loads(binding_old.read_text())
    second = subprocess.run(
        [BINARY_PATH, "seal-corpus", "--pool", POOL_PATH, "--binding", str(binding_new)],
        capture_output=True,
        text=True,
    )
    assert second.returncode == 0
    new_snapshot = json.loads(binding_new.read_text())
    assert new_snapshot["ingest_epoch"] > old_snapshot["ingest_epoch"]
    res = seal_bind_and_attest(
        POOL_PATH, ROOTS_PATH, "leaf-1", 3000, temp_output, binding_old, skip_seal=True
    )
    assert res.returncode != 0


def test_refusal_corpus_digest_tamper(built_binary, temp_output, tmp_path):
    """Attest-chain must reject pools whose on-disk content changed after seal-corpus digest binding."""
    pool_copy = write_pool(tmp_path, load_json(POOL_PATH))
    binding = tmp_path / "binding.json"
    sealed = subprocess.run(
        [BINARY_PATH, "seal-corpus", "--pool", str(pool_copy), "--binding", str(binding)],
        capture_output=True,
        text=True,
    )
    assert sealed.returncode == 0
    bound = subprocess.run(
        [BINARY_PATH, "bind-issuers", "--binding", str(binding)],
        capture_output=True,
        text=True,
    )
    assert bound.returncode == 0
    pool = load_json(pool_copy)
    pool[0]["subject"] = "CN=Tampered"
    with open(pool_copy, "w", encoding="utf-8") as handle:
        json.dump(pool, handle)
    res = seal_bind_and_attest(
        pool_copy,
        ROOTS_PATH,
        "leaf-1",
        3000,
        temp_output,
        binding,
        skip_seal=True,
        skip_bind=True,
    )
    assert res.returncode != 0


def test_attest_without_adjacency_fails(built_binary, temp_output, tmp_path):
    """Attest-chain must fail when issuer adjacency was never produced after seal-corpus."""
    binding = tmp_path / "binding.json"
    sealed = subprocess.run(
        [BINARY_PATH, "seal-corpus", "--pool", POOL_PATH, "--binding", str(binding)],
        capture_output=True,
        text=True,
    )
    assert sealed.returncode == 0
    adjacency_path = Path("/app/state/issuer_adjacency.json")
    adjacency_path.unlink(missing_ok=True)
    res = seal_bind_and_attest(
        POOL_PATH, ROOTS_PATH, "leaf-1", 3000, temp_output, binding, skip_seal=True, skip_bind=True
    )
    assert res.returncode != 0


def test_refusal_stale_adjacency_after_reseal(built_binary, temp_output, tmp_path):
    """Re-seal advances the ledger; an adjacency sealed for the prior epoch must be rejected."""
    binding_old = tmp_path / ("binding" + "-old.json")
    binding_new = tmp_path / ("binding" + "-new.json")
    first = subprocess.run(
        [BINARY_PATH, "seal-corpus", "--pool", POOL_PATH, "--binding", str(binding_old)],
        capture_output=True,
        text=True,
    )
    assert first.returncode == 0
    bind_old = subprocess.run(
        [BINARY_PATH, "bind-issuers", "--binding", str(binding_old)],
        capture_output=True,
        text=True,
    )
    assert bind_old.returncode == 0
    second = subprocess.run(
        [BINARY_PATH, "seal-corpus", "--pool", POOL_PATH, "--binding", str(binding_new)],
        capture_output=True,
        text=True,
    )
    assert second.returncode == 0
    # Intentionally skip bind-issuers after re-seal — prior adjacency epoch is stale for binding_new.
    res = seal_bind_and_attest(
        POOL_PATH,
        ROOTS_PATH,
        "leaf-1",
        3000,
        temp_output,
        binding_new,
        skip_seal=True,
        skip_bind=True,
    )
    assert res.returncode != 0


def test_refusal_adjacency_edge_tamper(built_binary, temp_output, tmp_path):
    """Attest-chain must reject an issuer adjacency whose edges no longer match fold_digest."""
    binding = tmp_path / "binding.json"
    sealed = subprocess.run(
        [BINARY_PATH, "seal-corpus", "--pool", POOL_PATH, "--binding", str(binding)],
        capture_output=True,
        text=True,
    )
    assert sealed.returncode == 0
    bound = subprocess.run(
        [BINARY_PATH, "bind-issuers", "--binding", str(binding)],
        capture_output=True,
        text=True,
    )
    assert bound.returncode == 0
    adjacency_path = Path("/app/state/issuer_adjacency.json")
    doc = json.loads(adjacency_path.read_text())
    # Drop one edge id without updating fold_digest.
    for subject, ids in list(doc["edges"].items()):
        if len(ids) > 1:
            doc["edges"][subject] = ids[1:]
            break
    adjacency_path.write_text(json.dumps(doc, indent=2))
    res = seal_bind_and_attest(
        POOL_PATH, ROOTS_PATH, "leaf-1", 3000, temp_output, binding, skip_seal=True, skip_bind=True
    )
    assert res.returncode != 0


def test_holdout_temporal_before_not_before(built_binary, temp_output, tmp_path):
    """Holdout pool: reject validation before certificate notBefore."""
    binding = tmp_path / "binding.json"
    res = seal_bind_and_attest(HIDDEN_POOL_PATH, HIDDEN_ROOTS_PATH, "leaf-1", 999, temp_output, binding)
    assert res.returncode != 0
    report = json.loads(temp_output.read_text())
    assert report["status"] == "failed"


def test_holdout_temporal_after_not_after(built_binary, temp_output, tmp_path):
    """Holdout pool: reject validation after an intermediate notAfter."""
    binding = tmp_path / "binding.json"
    pool = load_json(HOLDOUT_POOL_PATH)
    roots = load_json(HIDDEN_ROOTS_PATH)
    assert reference_reconstruct_path(pool, roots, _leaf_id(HOLDOUT_POOL_PATH, "exp", "late"), 5000) is None
    res = seal_bind_and_attest(
        HOLDOUT_POOL_PATH, HIDDEN_ROOTS_PATH, _leaf_id(HOLDOUT_POOL_PATH, "exp", "late"), 5000, temp_output, binding
    )
    assert res.returncode != 0
    report = json.loads(temp_output.read_text())
    assert report["status"] == "failed"


def test_holdout_lexicographic_path_selection(built_binary, temp_output, tmp_path):
    """Holdout pool: lex-smallest valid path wins among dual intermediates."""
    binding = tmp_path / "binding.json"
    pool = load_json(HOLDOUT_POOL_PATH)
    roots = load_json(HIDDEN_ROOTS_PATH)
    expected = reference_reconstruct_path(pool, roots, "leaf-dual", 3000)
    assert expected is not None
    res = seal_bind_and_attest(HOLDOUT_POOL_PATH, HIDDEN_ROOTS_PATH, "leaf-dual", 3000, temp_output, binding)
    assert res.returncode == 0
    chain = json.loads(temp_output.read_text())
    assert chain == expected


def test_holdout_multi_root_lex_selection(built_binary, temp_output, tmp_path):
    """Holdout pool: when two trusted roots are reachable, lex-min ID sequence wins."""
    binding = tmp_path / "binding.json"
    pool = load_json(HOLDOUT_POOL_PATH)
    roots = load_json(HIDDEN_ROOTS_PATH)
    expected = reference_reconstruct_path(pool, roots, _leaf_id(HOLDOUT_POOL_PATH, "mroot"), 3000)
    assert expected is not None
    res = seal_bind_and_attest(
        HOLDOUT_POOL_PATH, HIDDEN_ROOTS_PATH, _leaf_id(HOLDOUT_POOL_PATH, "mroot"), 3000, temp_output, binding
    )
    assert res.returncode == 0
    chain = json.loads(temp_output.read_text())
    assert chain == expected


def test_holdout_excluded_dns_lex_selection(built_binary, temp_output, tmp_path):
    """Holdout pool: lex-smaller intermediate excluded by NC; valid path uses int-exc-z."""
    binding = tmp_path / "binding.json"
    pool = load_json(HOLDOUT_POOL_PATH)
    roots = load_json(HIDDEN_ROOTS_PATH)
    expected = reference_reconstruct_path(pool, roots, _leaf_id(HOLDOUT_POOL_PATH, "exc", "select"), 3000)
    assert expected is not None
    res = seal_bind_and_attest(
        HOLDOUT_POOL_PATH, HIDDEN_ROOTS_PATH, _leaf_id(HOLDOUT_POOL_PATH, "exc", "select"), 3000, temp_output, binding
    )
    assert res.returncode == 0
    chain = json.loads(temp_output.read_text())
    assert chain == expected


def test_holdout_policy_path_selection(built_binary, temp_output, tmp_path):
    """Holdout corpus: lex-smaller intermediate fails policy; select next-valid chain."""
    binding = tmp_path / "binding.json"
    pool = load_json(HOLDOUT_POOL_PATH)
    roots = load_json(HIDDEN_ROOTS_PATH)
    expected = reference_reconstruct_path(pool, roots, _leaf_id(HOLDOUT_POOL_PATH, "policy", "select"), 3000)
    assert expected is not None
    res = seal_bind_and_attest(
        HOLDOUT_POOL_PATH, HIDDEN_ROOTS_PATH, _leaf_id(HOLDOUT_POOL_PATH, "policy", "select"), 3000, temp_output, binding
    )
    assert res.returncode == 0
    chain = json.loads(temp_output.read_text())
    assert chain == expected


def test_holdout_pathlen_rejects_lex_smaller(built_binary, temp_output, tmp_path):
    """Holdout: lex-preferred mid-pl-a path violates pathLen; only mid-pl-z is valid."""
    binding = tmp_path / "binding.json"
    pool = load_json(HOLDOUT_POOL_PATH)
    roots = load_json(HIDDEN_ROOTS_PATH)
    expected = reference_reconstruct_path(pool, roots, "leaf-pl-lex", 3000)
    assert expected is not None
    res = seal_bind_and_attest(HOLDOUT_POOL_PATH, HIDDEN_ROOTS_PATH, "leaf-pl-lex", 3000, temp_output, binding)
    assert res.returncode == 0
    chain = json.loads(temp_output.read_text())
    assert chain == expected


def test_holdout_tri_select_policy_and_name(built_binary, temp_output, tmp_path):
    """Holdout: int-tri-a fails policy, int-tri-m fails NC; only int-tri-z wins."""
    binding = tmp_path / "binding.json"
    pool = load_json(HOLDOUT_POOL_PATH)
    roots = load_json(HIDDEN_ROOTS_PATH)
    expected = reference_reconstruct_path(pool, roots, _leaf_id(HOLDOUT_POOL_PATH, "tri", "select"), 3000)
    assert expected is not None
    res = seal_bind_and_attest(
        HOLDOUT_POOL_PATH, HIDDEN_ROOTS_PATH, _leaf_id(HOLDOUT_POOL_PATH, "tri", "select"), 3000, temp_output, binding
    )
    assert res.returncode == 0
    chain = json.loads(temp_output.read_text())
    assert chain == expected


def test_holdout_explicit_policy_anypolicy_leaf_fails(built_binary, temp_output, tmp_path):
    """Holdout: leaf asserting only anyPolicy fails require_explicit_policy."""
    binding = tmp_path / "binding.json"
    pool = load_json(HOLDOUT_POOL_PATH)
    roots = load_json(HIDDEN_ROOTS_PATH)
    assert reference_reconstruct_path(pool, roots, _leaf_id(HOLDOUT_POOL_PATH, "explicit", "any"), 3000) is None
    res = seal_bind_and_attest(
        HOLDOUT_POOL_PATH, HIDDEN_ROOTS_PATH, _leaf_id(HOLDOUT_POOL_PATH, "explicit", "any"), 3000, temp_output, binding
    )
    assert res.returncode != 0
    report = json.loads(temp_output.read_text())
    assert report["status"] == "failed"


def test_holdout_nested_nc_intersection_fails(built_binary, temp_output, tmp_path):
    """Holdout: outer permits example.com but inner only other.com — must fail."""
    binding = tmp_path / "binding.json"
    pool = load_json(HOLDOUT_POOL_PATH)
    roots = load_json(HIDDEN_ROOTS_PATH)
    assert reference_reconstruct_path(pool, roots, _leaf_id(HOLDOUT_POOL_PATH, "nc", "intersect"), 3000) is None
    res = seal_bind_and_attest(
        HOLDOUT_POOL_PATH, HIDDEN_ROOTS_PATH, _leaf_id(HOLDOUT_POOL_PATH, "nc", "intersect"), 3000, temp_output, binding
    )
    assert res.returncode != 0
    report = json.loads(temp_output.read_text())
    assert report["status"] == "failed"


@pytest.mark.parametrize("target_id", HIDDEN_TARGETS)
def test_hidden_chain_matches_expected(built_binary, temp_output, tmp_path, target_id):
    """Each holdout target must match the chain oracle reconstructor."""
    binding = tmp_path / f"binding-{target_id}.json"
    pool = load_json(HIDDEN_POOL_PATH)
    roots = load_json(HIDDEN_ROOTS_PATH)
    expected = reference_reconstruct_path(pool, roots, target_id, 3000)
    assert expected is not None
    res = seal_bind_and_attest(HIDDEN_POOL_PATH, HIDDEN_ROOTS_PATH, target_id, 3000, temp_output, binding)
    assert res.returncode == 0
    chain = json.loads(temp_output.read_text())
    assert chain == expected
