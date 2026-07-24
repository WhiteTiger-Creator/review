"""Verifier tests for the MLflow registry Hugging Face metadata backfill task.

Each test maps to a functional_criteria[] entry in scaffold_plan.yaml. The system
under test is the Maven harness that unpacks the registry bundle, replays the Lua
migrations (including the newly-implemented V003 backfill) into an H2 database, and
writes a canonical JSONL export. The verifier re-runs that harness itself and grades the
regenerated export, rather than trusting any export the agent may have left on disk.

Run via tests/test.sh, which writes /logs/verifier/reward.txt from pytest's exit code.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest


# The harness root inside the container. environment/Dockerfile does `COPY harness/ /app/`
# with `WORKDIR /app`, so /app/pom.xml, /app/migrations/, /app/expected/ and the bundle
# all resolve here. Fall back to an upward pom.xml search if the harness is mounted
# elsewhere, so the tests are not silently coupled to a single mount point.
def _discover_harness_dir() -> Path:
    candidate = Path("/app")
    if (candidate / "pom.xml").is_file():
        return candidate
    cursor = Path.cwd().resolve()
    while cursor != cursor.parent:
        if (cursor / "pom.xml").is_file():
            return cursor
        cursor = cursor.parent
    return Path("/app")


HARNESS_DIR = _discover_harness_dir()
POM = HARNESS_DIR / "pom.xml"
EXPORT_PATH = HARNESS_DIR / "target" / "registry_export.jsonl"
EXPECTED_DIGEST_PATH = HARNESS_DIR / "expected" / "registry_export.sha256"
V003_PATH = HARNESS_DIR / "migrations" / "V003_backfill_hf_model_metadata.lua"

# The sealed data service (see com.example.registry.SealedDataService and
# environment/sealed/data_service.py) is the only source of the pinned Hugging Face
# config fixtures; there is no on-disk cache to read anymore. `environment_mode = "shared"`
# means this verifier runs in the same container the agent's `mvn package`/`mvn test`
# calls already ran in, so by the time these tests execute (after the harness_exports
# fixture has invoked the harness at least once) the service is already up.
SEALED_SERVICE_BASE_URL = "http://127.0.0.1:8743"
_HTTP_NOT_FOUND = 404

_HEX64 = re.compile(r"\b([0-9a-fA-F]{64})\b")

# Matches each `(model_name, version, source_run_id, parent_version, current_stage)`
# tuple in the seed SQL's model_versions INSERT blocks; used to check the backfill
# against the actual original lineage rather than a fixed list of known-bad values.
_SEED_LINEAGE_ROW = re.compile(
    r"\('([^']+)',\s*(\d+),\s*'([^']+)',\s*(NULL|\d+),\s*'[^']*'\)"
)

# Build offline (~/.m2 is pre-warmed at image-build time) and skip the project's own
# JUnit suite so the export is produced by the harness runner regardless of whether the
# agent-editable tests pass. Grading is done by the verifier-owned assertions below.
_MVN_PACKAGE = [
    "mvn", "-B", "-o", "-q",
    "-f", str(POM),
    "package", "-Dmaven.test.skip=true",
]
_MVN_TEST = ["mvn", "-B", "-o", "-q", "-f", str(POM), "test"]


def _reset_fetch_log() -> None:
    """Clear the sealed service's record of which config URLs have been fetched, so the
    next harness run's record only reflects that run. A ConnectionError here just means
    the sealed service hasn't been started by any prior mvn invocation yet, in which case
    its fetch log is already empty and there's nothing to reset."""
    try:
        urllib.request.urlopen(f"{SEALED_SERVICE_BASE_URL}/reset", timeout=10)
    except urllib.error.URLError:
        pass


def _fetched_urls() -> set[str]:
    """URLs actually queried through the sealed service's /hf-config endpoint (i.e. via
    http.get, the only path that reaches it) since the last reset."""
    with urllib.request.urlopen(f"{SEALED_SERVICE_BASE_URL}/fetched-urls", timeout=10) as response:
        return set(json.loads(response.read().decode("utf-8")))


def _run_harness() -> subprocess.CompletedProcess:
    """Regenerate target/registry_export.jsonl from the current migrations."""
    if EXPORT_PATH.exists():
        EXPORT_PATH.unlink()  # never grade a stale export from a previous run
    _reset_fetch_log()
    return subprocess.run(
        _MVN_PACKAGE,
        cwd=str(HARNESS_DIR),
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )


@pytest.fixture(scope="session")
def harness_exports() -> dict:
    """Run the full harness pipeline twice and capture both canonical exports.

    Two independent runs let the idempotency / determinism tests compare byte-for-byte;
    the parsed rows from the first run feed the correctness assertions. The fetch log is
    captured after each run too, so a separate test can confirm the migration actually
    called http.get for every pinned model rather than reconstructing the answer some
    other way (e.g. from memorized knowledge of well-known model architectures).
    """
    first = _run_harness()
    assert first.returncode == 0, (
        f"harness `mvn package` failed on run 1:\n{first.stdout}\n{first.stderr}"
    )
    assert EXPORT_PATH.is_file(), "harness did not produce target/registry_export.jsonl"
    first_bytes = EXPORT_PATH.read_bytes()
    first_fetched = _fetched_urls()

    second = _run_harness()
    assert second.returncode == 0, (
        f"harness `mvn package` failed on run 2:\n{second.stdout}\n{second.stderr}"
    )
    assert EXPORT_PATH.is_file(), "harness did not reproduce the export on the second run"
    second_bytes = EXPORT_PATH.read_bytes()
    second_fetched = _fetched_urls()

    registered, versions = _parse_export(first_bytes.decode("utf-8"))
    return {
        "first_bytes": first_bytes,
        "second_bytes": second_bytes,
        "registered_models": registered,
        "model_versions": versions,
        "first_fetched_urls": first_fetched,
        "second_fetched_urls": second_fetched,
    }


def _parse_export(text: str) -> tuple[list[dict], list[dict]]:
    """Split the JSONL export into (registered_models, model_versions) record lists."""
    registered: list[dict] = []
    versions: list[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        record = json.loads(line)  # each line must be a valid JSON object
        table = record.get("table")
        if table == "registered_models":
            registered.append(record)
        elif table == "model_versions":
            versions.append(record)
    return registered, versions


def _expected_digest() -> str:
    raw = EXPECTED_DIGEST_PATH.read_text(encoding="utf-8").strip()
    match = _HEX64.search(raw)
    assert match, f"expected digest file is not a 64-hex SHA-256: {raw!r}"
    return match.group(1).lower()


def _load_seed_lineage() -> dict[tuple[str, int], tuple[str, int | None]]:
    """(model_name, version) -> (source_run_id, parent_version) as originally seeded,
    parsed straight out of the seed SQL served by the sealed data service. Lets the
    lineage test check the backfill against the real original values instead of a fixed
    list of placeholder strings a particular bad implementation might happen to use."""
    with urllib.request.urlopen(f"{SEALED_SERVICE_BASE_URL}/seed", timeout=10) as response:
        seed_sql = response.read().decode("utf-8")
    lineage: dict[tuple[str, int], tuple[str, int | None]] = {}
    for model_name, version, source_run_id, parent_version in _SEED_LINEAGE_ROW.findall(seed_sql):
        parent = None if parent_version == "NULL" else int(parent_version)
        lineage[(model_name, int(version))] = (source_run_id, parent)
    return lineage


def _load_cached_config(repo_id: str, revision: str) -> dict | None:
    """Query the sealed data service for a model's pinned Hub config by exact URL, the
    same way HubConfigClient.java does. Returns None if that URL isn't pinned."""
    url = f"https://huggingface.co/{repo_id}/resolve/{revision}/config.json"
    query = urllib.parse.urlencode({"url": url})
    request = urllib.request.Request(f"{SEALED_SERVICE_BASE_URL}/hf-config?{query}")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == _HTTP_NOT_FOUND:
            return None
        raise


def _normalize_config(config: dict) -> dict:
    """Mirror the intended V003 normalization: architecture falls back to model_type
    (whether "architectures" is absent or present-but-empty), and each numeric field is
    resolved across the alternative key spellings used by the different model families
    (BERT/BART, GPT-2, DistilBERT, T5), then the nested text_config block, in a fixed
    order. Decoy fields that sit alongside the real ones (T5's num_decoder_layers, GQA's
    num_key_value_heads) are deliberately excluded from the alias lists. When no
    head-count field is present under any spelling (Falcon-style configs give only
    head_dim), the head count is derived from hidden_size / head_dim."""

    def resolve(*keys: str):
        for key in keys:
            if config.get(key) is not None:
                return config[key]
        text_config = config.get("text_config") or {}
        return text_config.get(keys[0])

    architectures = config.get("architectures")
    architecture = architectures[0] if architectures else config.get("model_type")
    hidden_size = resolve("hidden_size", "dim", "n_embd", "d_model")
    num_heads = resolve("num_attention_heads", "n_heads", "n_head", "num_heads")
    if num_heads is None and config.get("head_dim") is not None and hidden_size is not None:
        num_heads = hidden_size // config["head_dim"]
    return {
        "hf_architecture": architecture,
        "hf_model_type": config.get("model_type"),
        "hf_hidden_size": hidden_size,
        "hf_num_layers": resolve("num_hidden_layers", "n_layers", "n_layer", "num_layers"),
        "hf_num_heads": num_heads,
    }


def test_export_sha256_matches_expected(harness_exports):
    """functional_criteria[id=export_sha256_matches_expected]: SHA-256 of the regenerated
    export equals the digest committed in expected/registry_export.sha256."""
    actual = hashlib.sha256(harness_exports["first_bytes"]).hexdigest().lower()
    assert actual == _expected_digest(), (
        "sha256 of the migrated registry_export.jsonl did not match the expected digest"
    )


def test_migration_is_idempotent(harness_exports):
    """functional_criteria[id=migration_is_idempotent]: replaying the full harness twice
    (a fresh unpack + reseed each time, then the migrations) must yield a byte-identical
    export, i.e. the backfill implementation is a pure function of its inputs with no
    accumulating side effect across applications."""
    assert harness_exports["first_bytes"] == harness_exports["second_bytes"], (
        "re-running the harness produced a different export (non-deterministic or "
        "non-idempotent migration)"
    )


def test_model_lineage_preserved(harness_exports):
    """functional_criteria[id=model_lineage_preserved]: every model_versions row keeps its
    original source_run_id/parent_version exactly as seeded; the backfill must only touch
    the hf_* metadata columns, never lineage, and must not add or drop any version row."""
    versions = harness_exports["model_versions"]
    assert versions, "export contains no model_versions rows"
    seed_lineage = _load_seed_lineage()
    assert seed_lineage, "could not parse any lineage rows out of the seed SQL"

    broken = []
    for v in versions:
        key = (v.get("model_name"), v.get("version"))
        expected = seed_lineage.get(key)
        actual = (v.get("source_run_id"), v.get("parent_version"))
        if expected is None or actual != expected:
            broken.append({"row": v, "expected_lineage": expected})
    assert not broken, (
        f"model_versions rows don't match their original seeded lineage: {broken}"
    )
    assert len(versions) == len(seed_lineage), (
        f"expected {len(seed_lineage)} model_versions rows (one per seeded version), "
        f"got {len(versions)}"
    )


def test_hf_config_metadata_backfilled(harness_exports):
    """functional_criteria[id=hf_config_metadata_backfilled]: each model's versions carry
    the normalized Hub config of that same model (correct model-to-config association),
    resolved through the documented key-fallback + nested text_config rules."""
    registered = harness_exports["registered_models"]
    versions = harness_exports["model_versions"]
    assert registered, "export contains no registered_models rows"

    versions_by_model: dict[str, list[dict]] = {}
    for v in versions:
        versions_by_model.setdefault(v.get("model_name"), []).append(v)

    checked = 0
    for model in registered:
        repo_id = model.get("hf_repo_id")
        revision = model.get("hf_revision")
        if not repo_id or not revision:
            continue
        config = _load_cached_config(repo_id, revision)
        assert config is not None, (
            f"missing pinned Hub config cache for {model.get('name')} "
            f"({repo_id}@{revision}); offline grading requires it"
        )
        expected = _normalize_config(config)

        model_versions = versions_by_model.get(model.get("name"), [])
        assert model_versions, f"no model_versions rows for model {model.get('name')!r}"
        for v in model_versions:
            for column, want in expected.items():
                assert v.get(column) == want, (
                    f"model {model.get('name')!r} version {v.get('version')} has "
                    f"{column}={v.get(column)!r}, expected its own config's {want!r}"
                )
        checked += 1

    assert checked > 0, "no pinned models were cross-checked against their Hub config"


def test_http_helper_used_for_every_pinned_model(harness_exports):
    """functional_criteria[id=http_helper_used_for_every_pinned_model]: the migration
    actually calls http.get for every pinned model's config on every run, rather than
    reconstructing the correct metadata some other way (e.g. hardcoding values recalled
    from a well-known architecture's real published config instead of reading what this
    fixture's own config.json actually contains). Checked on both harness runs, since a
    migration could satisfy this on a first "exploratory" run and then skip the fetch on
    a cached/memoized second run, which would defeat the point of the check."""
    registered = harness_exports["registered_models"]
    pinned_urls = {
        f"https://huggingface.co/{model['hf_repo_id']}/resolve/{model['hf_revision']}/config.json"
        for model in registered
        if model.get("hf_repo_id") and model.get("hf_revision")
    }
    assert pinned_urls, "no pinned models found in the export"

    for label, fetched in (
        ("first", harness_exports["first_fetched_urls"]),
        ("second", harness_exports["second_fetched_urls"]),
    ):
        missing = pinned_urls - fetched
        assert not missing, (
            f"migration did not call http.get for these pinned models' configs during "
            f"the {label} harness run: {sorted(missing)}"
        )


def test_canonical_export_order(harness_exports):
    """functional_criteria[id=canonical_export_order]: the export lists tables in a fixed
    canonical order with deterministic row ordering, so the digest is stable across runs."""
    text = harness_exports["first_bytes"].decode("utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert lines, "export is empty"

    tables = [json.loads(ln)["table"] for ln in lines]
    # Fixed table order: every registered_models record precedes every model_versions one.
    last_registered = max(
        (i for i, t in enumerate(tables) if t == "registered_models"), default=-1
    )
    first_versions = next(
        (i for i, t in enumerate(tables) if t == "model_versions"), len(tables)
    )
    assert last_registered < first_versions, (
        "canonical table order violated: model_versions rows interleave with "
        "registered_models rows"
    )

    registered = harness_exports["registered_models"]
    versions = harness_exports["model_versions"]
    # Deterministic row order within each table (primary-key sorted).
    reg_names = [r["name"] for r in registered]
    assert reg_names == sorted(reg_names), (
        f"registered_models rows are not sorted by name: {reg_names}"
    )
    version_keys = [(v["model_name"], v["version"]) for v in versions]
    assert version_keys == sorted(version_keys), (
        f"model_versions rows are not sorted by (model_name, version): {version_keys}"
    )

    # Determinism across runs is what makes the digest reproducible.
    assert harness_exports["first_bytes"] == harness_exports["second_bytes"], (
        "canonical export is not byte-stable across runs; the digest would drift"
    )


def test_uses_provided_apis_not_raw_sql():
    """functional_criteria[id=uses_provided_apis_not_raw_sql]: the V003 migration reaches
    the database and the Hub only through the provided db/http helpers, never by reading
    the seed SQL or opening files/sockets/processes directly."""
    assert V003_PATH.is_file(), f"migration not found: {V003_PATH}"
    source = V003_PATH.read_text(encoding="utf-8")

    # Escape hatches that would bypass the provided bridge (direct file / process / socket
    # / dynamic-load access) or read harness-internal artifacts directly.
    forbidden = [
        "io.open", "io.read", "io.lines", "io.popen", "io.input", "io.write",
        "os.execute", "os.getenv", "os.remove", "os.rename", "os.tmpname", "popen",
        "dofile", "loadfile", "require", "package.", "luasql", "socket.",
        "registry_seed", ".mv.db", "hf_config_cache", "target/bundle",
    ]
    offenders = [token for token in forbidden if token in source]
    assert not offenders, (
        f"V003 migration bypasses the provided db/http helpers or reads harness "
        f"internals directly via: {offenders}"
    )

    # The implemented migration must actually use the provided DB and HTTP helpers.
    assert "db." in source, "V003 does not use the provided db helper"
    assert "http.get" in source, "V003 does not use the provided http.get helper"


def test_mlflow_registry_harness_java_tests():
    """code_projects[id=mlflow_registry_harness]: the project's JUnit harness suite passes
    once the migration is implemented (supporting end-to-end signal alongside the
    verifier-owned export checks above)."""
    result = subprocess.run(
        _MVN_TEST,
        cwd=str(HARNESS_DIR),
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    assert result.returncode == 0, (
        f"project JUnit harness suite still failing:\n{result.stdout}\n{result.stderr}"
    )
