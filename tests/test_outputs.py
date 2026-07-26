"""Verifier for the Hugging Face architecture backfill task.

Grading has three layers, and only the first needs any notion of a correct answer:

1. **Digest.** The SHA-256 of the regenerated canonical export must equal the digest
   recorded at image-build time by a reference implementation that is not present in the
   shipped image. It is kept in the root-owned sealed directory rather than in the project
   tree, so the account doing the work cannot rewrite the value it is checked against.

2. **Perturbation battery.** The bulk of the grading. The verifier mutates one field of one
   checkpoint config, re-runs the harness, and asserts how the export *responds*: which
   values track the change, which are provably unaffected, and which rows must not move at
   all. These assertions need no answer key -- they check the causal structure of the
   computation, which is exactly the thing a hardcoded or half-derived implementation
   cannot fake. An implementation that memorized the corpus fails here even though it
   passes layer 1 on the unperturbed run.

3. **Structural invariants.** Scope, lineage, dedup, idempotency, and the sandbox rules.

Deliberately absent: any reference normalizer, expected field values, or per-model
architecture data. Nothing in this file tells a reader what a correct row contains.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest


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
# The expected digest lives in the root-owned sealed directory, not in the project tree.
# The agent owns /app and could otherwise replace the file the grader compares against
# (owning the parent directory defeats a read-only file just as well as owning the file).
EXPECTED_DIGEST_PATH = Path("/opt/_sealed/registry_export.sha256")
V003_PATH = HARNESS_DIR / "migrations" / "V003_backfill_hf_model_metadata.lua"

SERVICE = "http://127.0.0.1:8743"

_HEX64 = re.compile(r"\b([0-9a-fA-F]{64})\b")
_SEED_VERSION_ROW = re.compile(
    r"\('([^']+)',\s*(\d+),\s*'([^']+)',\s*(NULL|\d+),\s*'([^']*)',\s*(NULL|'[0-9a-f]+')\)"
)
_SEED_MODEL_ROW = re.compile(r"\('([^']+)',\s*(\d+),\s*'((?:[^']|'')*)',\s*'([^']+)'\)")

_MVN_PACKAGE = ["mvn", "-B", "-o", "-q", "-f", str(POM), "package", "-Dmaven.test.skip=true"]
_MVN_TEST = ["mvn", "-B", "-o", "-q", "-f", str(POM), "test"]


# --------------------------------------------------------------------------------------
# Sealed service plumbing
# --------------------------------------------------------------------------------------

def _service_get(path: str) -> str:
    with urllib.request.urlopen(SERVICE + path, timeout=20) as response:
        return response.read().decode("utf-8")


def _perturb(repo: str, field: str, value) -> None:
    """Override one config field for one repo on the next fetch. value=None deletes it."""
    query = {"repo": repo, "field": field}
    if value is not None:
        query["value"] = json.dumps(value)
    _service_get("/control/perturb?" + urllib.parse.urlencode(query))


def _clear_perturbations() -> None:
    _service_get("/control/clear")


def _pinned() -> list[dict]:
    return json.loads(_service_get("/control/pinned"))


def _fetched_urls() -> set[str]:
    return set(json.loads(_service_get("/fetched-urls")))


def _seed_sql() -> str:
    return _service_get("/seed")


def _load_config(pin: dict) -> dict:
    """The unperturbed config document for a pin, as the migration would receive it. Used
    only to read a field's CURRENT value so a perturbation can be expressed as a delta;
    never to compute an expected output."""
    query = urllib.parse.urlencode({"url": pin["config_url"]})
    with urllib.request.urlopen(f"{SERVICE}/hf?{query}", timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


# --------------------------------------------------------------------------------------
# Harness driving
# --------------------------------------------------------------------------------------

def _run_harness() -> tuple[bytes, dict]:
    """Regenerate the export and return (raw bytes, parsed tables)."""
    if EXPORT_PATH.exists():
        EXPORT_PATH.unlink()
    result = subprocess.run(_MVN_PACKAGE, cwd=str(HARNESS_DIR), capture_output=True,
                            text=True, timeout=300, check=False)
    assert result.returncode == 0, (
        f"harness `mvn package` failed:\n{result.stdout}\n{result.stderr}")
    assert EXPORT_PATH.is_file(), "harness did not produce target/registry_export.jsonl"
    raw = EXPORT_PATH.read_bytes()
    return raw, _parse(raw.decode("utf-8"))


def _parse(text: str) -> dict:
    tables: dict[str, list[dict]] = {
        "registered_models": [], "model_architecture": [], "model_versions": []}
    order: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        table = record["table"]
        order.append(table)
        tables.setdefault(table, []).append(record)
    tables["_order"] = order
    return tables


def _models_by_name(tables: dict) -> dict[str, dict]:
    return {r["name"]: r for r in tables["registered_models"]}


def _arch_by_fingerprint(tables: dict) -> dict[str, dict]:
    return {r["fingerprint"]: r for r in tables["model_architecture"]}


def _versions_by_model(tables: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for row in tables["model_versions"]:
        out.setdefault(row["model_name"], []).append(row)
    return out


def _arch_of(tables: dict, model: str) -> dict:
    """The architecture row a model's versions point at."""
    versions = _versions_by_model(tables).get(model, [])
    assert versions, f"no model_versions rows for {model!r}"
    fingerprints = {v["hf_architecture_fingerprint"] for v in versions}
    assert len(fingerprints) == 1, (
        f"{model!r} versions disagree on hf_architecture_fingerprint: {fingerprints}")
    fingerprint = fingerprints.pop()
    assert fingerprint is not None, f"{model!r} has no architecture fingerprint"
    arch = _arch_by_fingerprint(tables).get(fingerprint)
    assert arch is not None, (
        f"{model!r} references fingerprint {fingerprint} with no model_architecture row")
    return arch


# --------------------------------------------------------------------------------------
# Repo <-> model mapping, taken from the pin inventory rather than hardcoded here.
# --------------------------------------------------------------------------------------

@pytest.fixture(scope="session")
def pins() -> dict:
    inventory = _pinned()
    return {
        "by_model": {p["model"]: p for p in inventory},
        "by_repo": {p["repo"]: p for p in inventory},
        "in_scope": [p for p in inventory if p["framework"] == "transformers"],
    }


@pytest.fixture(scope="session")
def baseline() -> dict:
    """Unperturbed run. Everything else compares against this.

    Runs the harness before making any direct call to the sealed service: the service is
    started lazily, the first time the harness's SeedDatabaseLoader touches it, and nothing
    guarantees it is already running when this fixture is first instantiated (e.g. an oracle
    run that only drops in a migration file and never invokes Maven itself). Calling
    `_clear_perturbations()` first would hit a port nothing is listening on yet.
    """
    raw, tables = _run_harness()
    _clear_perturbations()
    fetched = _fetched_urls()
    second_raw, _ = _run_harness()
    return {"raw": raw, "tables": tables, "fetched": fetched, "second_raw": second_raw}


@pytest.fixture
def perturbed():
    """Apply perturbations, run once, then always clear.

    Usage: `tables = perturbed([(repo, field, value), ...])`
    """
    applied = False

    def _apply(changes):
        nonlocal applied
        applied = True
        _clear_perturbations()
        for repo, field, value in changes:
            _perturb(repo, field, value)
        _, tables = _run_harness()
        return tables

    yield _apply
    if applied:
        _clear_perturbations()


# --------------------------------------------------------------------------------------
# Layer 1 -- digest
# --------------------------------------------------------------------------------------

def test_export_matches_expected_digest(baseline):
    """The regenerated export matches the digest committed at image-build time."""
    expected = _HEX64.search(EXPECTED_DIGEST_PATH.read_text(encoding="utf-8").strip())
    assert expected, "expected digest file is not a 64-hex SHA-256"
    actual = hashlib.sha256(baseline["raw"]).hexdigest().lower()
    assert actual == expected.group(1).lower(), (
        "sha256 of the regenerated export did not match the expected digest")


def test_export_is_byte_stable(baseline):
    """Two full harness runs produce identical bytes."""
    assert baseline["raw"] == baseline["second_raw"], (
        "re-running the harness produced a different export")


# --------------------------------------------------------------------------------------
# Layer 2 -- perturbation battery
# --------------------------------------------------------------------------------------

def _assert_only_changed(before: dict, after: dict, changed_models: set[str]):
    """Every model outside `changed_models` must have a byte-identical architecture row and
    identical version rows."""
    before_versions = _versions_by_model(before)
    after_versions = _versions_by_model(after)
    assert set(before_versions) == set(after_versions), "model set changed under perturbation"

    drifted = []
    for model in before_versions:
        if model in changed_models:
            continue
        if before_versions[model] != after_versions[model]:
            drifted.append(model)
            continue
        try:
            before_arch = _arch_of(before, model)
            after_arch = _arch_of(after, model)
        except AssertionError:
            continue
        if before_arch != after_arch:
            drifted.append(model)
    assert not drifted, (
        f"perturbing {sorted(changed_models)} also changed unrelated models: {sorted(drifted)}. "
        "Each model's architecture must derive only from its own checkpoint config.")


def test_depth_perturbation_propagates(baseline, pins, perturbed):
    """Changing a checkpoint's layer count must move exactly the quantities that depend on
    depth, scale the KV cache proportionally, and leave every other model untouched."""
    repo = pins["by_model"]["qa-encoder"]["repo"]
    before = _arch_of(baseline["tables"], "qa-encoder")
    new_layers = before["num_layers"] + 7

    after_tables = perturbed([(repo, "num_hidden_layers", new_layers)])
    after = _arch_of(after_tables, "qa-encoder")

    assert after["num_layers"] == new_layers, "num_layers did not track the config"
    assert after["hidden_size"] == before["hidden_size"], "depth must not change width"
    assert after["num_heads"] == before["num_heads"], "depth must not change head count"
    assert after["fingerprint"] != before["fingerprint"], "fingerprint ignored the change"

    # KV cache is per-layer, so it scales exactly with depth.
    assert (after["kv_cache_bytes_per_token"] * before["num_layers"]
            == before["kv_cache_bytes_per_token"] * new_layers), (
        "kv_cache_bytes_per_token did not scale proportionally with depth "
        f"({before['kv_cache_bytes_per_token']} at {before['num_layers']} layers vs "
        f"{after['kv_cache_bytes_per_token']} at {new_layers})")

    # Parameters grow with depth, but not proportionally: embeddings are depth-independent,
    # so the ratio must be strictly less than the depth ratio.
    assert after["total_param_count"] > before["total_param_count"]
    assert (after["total_param_count"] * before["num_layers"]
            < before["total_param_count"] * new_layers), (
        "total_param_count scaled proportionally with depth, which means depth-independent "
        "parameters (embeddings) are being counted per layer or not at all")

    _assert_only_changed(baseline["tables"], after_tables, {"qa-encoder"})


def test_dtype_affects_cache_but_not_parameter_count(baseline, pins, perturbed):
    """torch_dtype is a storage width. It changes how many *bytes* a cached token occupies
    and nothing else -- parameter counts are counts, not sizes."""
    repo = pins["by_model"]["reranker"]["repo"]
    before = _arch_of(baseline["tables"], "reranker")

    after_tables = perturbed([(repo, "torch_dtype", "float32")])
    after = _arch_of(after_tables, "reranker")

    assert after["total_param_count"] == before["total_param_count"], (
        "total_param_count changed with torch_dtype; a parameter count must not depend on "
        "the width it is stored at")
    assert after["active_param_count"] == before["active_param_count"]
    assert after["hidden_size"] == before["hidden_size"]
    assert after["num_layers"] == before["num_layers"]
    assert after["kv_cache_bytes_per_token"] == before["kv_cache_bytes_per_token"] * 2, (
        "moving a bfloat16 checkpoint to float32 must exactly double the per-token cache")
    assert after["fingerprint"] != before["fingerprint"]

    _assert_only_changed(baseline["tables"], after_tables, {"reranker"})


def test_kv_head_perturbation(baseline, pins, perturbed):
    """Key-value head count drives the cache, the attention variant, and -- because K and V
    projections are sized by it -- the parameter count. It must not touch the width."""
    repo = pins["by_model"]["doc-classifier"]["repo"]
    before = _arch_of(baseline["tables"], "doc-classifier")
    assert before["num_kv_heads"] > 1, "fixture precondition: expected grouped-query"

    after_tables = perturbed([(repo, "num_key_value_heads", 1)])
    after = _arch_of(after_tables, "doc-classifier")

    assert after["num_kv_heads"] == 1
    assert after["attention_variant"] == "mqa", (
        f"one key-value head is multi-query attention, got {after['attention_variant']!r}")
    assert after["num_heads"] == before["num_heads"], "query head count must not move"
    assert after["hidden_size"] == before["hidden_size"], "residual width must not move"
    assert (after["kv_cache_bytes_per_token"] * before["num_kv_heads"]
            == before["kv_cache_bytes_per_token"]), (
        "per-token cache did not scale with the key-value head count")
    assert after["total_param_count"] < before["total_param_count"], (
        "narrowing the K and V projections must reduce the parameter count; unchanged means "
        "attention is being sized by the query head count alone")

    _assert_only_changed(baseline["tables"], after_tables, {"doc-classifier"})


def test_query_heads_alone_do_not_change_cache(baseline, pins, perturbed):
    """Holding the key-value head count and the head width fixed while changing the query
    head count must leave the cache alone. This is the converse of the previous check and
    fails any implementation that sizes the cache by query heads."""
    repo = pins["by_model"]["doc-classifier"]["repo"]
    before = _arch_of(baseline["tables"], "doc-classifier")
    kv = before["num_kv_heads"]

    # head_dim is pinned to its current value alongside the head-count change: this
    # checkpoint does not declare one, so it would otherwise be re-derived from the new
    # query head count and the cache would move for that reason instead.
    after_tables = perturbed([(repo, "num_attention_heads", kv),
                              (repo, "head_dim", before["head_dim"])])
    after = _arch_of(after_tables, "doc-classifier")

    assert after["num_heads"] == kv
    assert after["head_dim"] == before["head_dim"]
    assert after["attention_variant"] == "mha", (
        "equal query and key-value head counts is plain multi-head attention")
    assert after["kv_cache_bytes_per_token"] == before["kv_cache_bytes_per_token"], (
        "per-token cache moved when only the query head count changed; the cache holds keys "
        "and values, not queries")
    assert after["total_param_count"] < before["total_param_count"], (
        "narrowing the query projections must reduce the parameter count")

    _assert_only_changed(baseline["tables"], after_tables, {"doc-classifier"})


def test_expert_routing_moves_active_not_total(baseline, pins, perturbed):
    """For a mixture-of-experts checkpoint, how many experts each token is routed to
    changes the active parameter count and nothing else. Total counts every expert
    regardless of routing."""
    repo = pins["by_model"]["chat-assistant"]["repo"]
    before = _arch_of(baseline["tables"], "chat-assistant")
    assert before["active_param_count"] < before["total_param_count"], (
        "fixture precondition: expected a sparse mixture-of-experts checkpoint")

    # Pin the expert count and vary only the routing width, so the comparison holds no
    # matter what the unperturbed checkpoint happens to declare.
    narrow = perturbed([(repo, "num_local_experts", 4), (repo, "num_experts_per_tok", 1)])
    narrow_arch = _arch_of(narrow, "chat-assistant")
    wide = perturbed([(repo, "num_local_experts", 4), (repo, "num_experts_per_tok", 3)])
    wide_arch = _arch_of(wide, "chat-assistant")

    assert narrow_arch["total_param_count"] == wide_arch["total_param_count"], (
        "total_param_count changed with the routing width; total must count every expert "
        "regardless of how many are engaged per token")
    assert narrow_arch["active_param_count"] < wide_arch["active_param_count"], (
        "active_param_count ignored the routing width; routing to three experts must "
        "engage more parameters per token than routing to one")
    assert wide_arch["active_param_count"] < wide_arch["total_param_count"], (
        "routing to three of four experts must still be sparse")
    assert narrow_arch["hidden_size"] == before["hidden_size"]
    assert narrow_arch["num_layers"] == before["num_layers"]

    _assert_only_changed(baseline["tables"], wide, {"chat-assistant"})


def test_expert_count_moves_total(baseline, pins, perturbed):
    """Adding experts raises the total parameter count far faster than it raises the active
    count: every added expert is counted in full by total, while a token still runs the same
    number of them."""
    repo = pins["by_model"]["chat-assistant"]["repo"]
    before = _arch_of(baseline["tables"], "chat-assistant")

    few = perturbed([(repo, "num_local_experts", 3), (repo, "num_experts_per_tok", 2)])
    few_arch = _arch_of(few, "chat-assistant")
    many = perturbed([(repo, "num_local_experts", 6), (repo, "num_experts_per_tok", 2)])
    many_arch = _arch_of(many, "chat-assistant")

    total_growth = many_arch["total_param_count"] - few_arch["total_param_count"]
    active_growth = many_arch["active_param_count"] - few_arch["active_param_count"]

    assert total_growth > 0, "raising the expert count must raise the total parameter count"
    assert active_growth * 10 < total_growth, (
        "doubling the number of available experts moved the active parameter count almost "
        f"as much as the total (active +{active_growth}, total +{total_growth}). At a fixed "
        "routing width the same number of experts runs per token; only the router widens.")
    assert many_arch["hidden_size"] == before["hidden_size"]
    assert many_arch["num_layers"] == before["num_layers"]
    assert many_arch["ffn_dim"] == before["ffn_dim"]

    _assert_only_changed(baseline["tables"], many, {"chat-assistant"})


def test_top_level_declaration_wins_over_nested(baseline, pins, perturbed):
    """A checkpoint that declares a quantity both at the top level and inside text_config
    must resolve to the top-level value."""
    repo = pins["by_model"]["ocr-reader"]["repo"]
    before = _arch_of(baseline["tables"], "ocr-reader")
    new_layers = before["num_layers"] + 5

    after_tables = perturbed([(repo, "num_hidden_layers", new_layers)])
    after = _arch_of(after_tables, "ocr-reader")

    assert after["num_layers"] == new_layers, (
        "changing the top-level num_hidden_layers had no effect, so the nested text_config "
        "value is being preferred over the top-level one")

    _assert_only_changed(baseline["tables"], after_tables, {"ocr-reader"})


def test_vision_tower_is_ignored(baseline, pins, perturbed):
    """For a dual-tower checkpoint, the resolved architecture describes the language-model
    backbone. Perturbing the vision tower must change nothing at all."""
    repo = pins["by_model"]["vision-captioner"]["repo"]
    before = _arch_of(baseline["tables"], "vision-captioner")

    after_tables = perturbed([
        (repo, "vision_config.hidden_size", before["hidden_size"] * 2 + 64),
        (repo, "vision_config.num_hidden_layers", 99),
        (repo, "vision_config.num_attention_heads", 7),
    ])
    after = _arch_of(after_tables, "vision-captioner")

    assert after == before, (
        "perturbing the vision tower changed the resolved architecture; every quantity must "
        "come from the language-model backbone")
    _assert_only_changed(baseline["tables"], after_tables, set())


def test_backbone_inside_text_config_is_used(baseline, pins, perturbed):
    """The converse: for the same dual-tower checkpoint, the nested backbone *is* the
    source, so perturbing it must propagate."""
    repo = pins["by_model"]["vision-captioner"]["repo"]
    before = _arch_of(baseline["tables"], "vision-captioner")
    new_layers = before["num_layers"] + 3

    after_tables = perturbed([(repo, "text_config.num_hidden_layers", new_layers)])
    after = _arch_of(after_tables, "vision-captioner")

    assert after["num_layers"] == new_layers, (
        "the language-model backbone inside text_config was not used")
    _assert_only_changed(baseline["tables"], after_tables, {"vision-captioner"})


def test_absent_ffn_width_falls_back_to_library_default(baseline, pins, perturbed):
    """A feed-forward width the config omits is supplied by the library's default, not left
    unresolved."""
    repo = pins["by_model"]["doc-classifier"]["repo"]
    before = _arch_of(baseline["tables"], "doc-classifier")

    after_tables = perturbed([(repo, "intermediate_size", None)])
    after = _arch_of(after_tables, "doc-classifier")

    assert after["ffn_dim"] is not None, (
        "ffn_dim came back null; an omitted feed-forward width has a library default")
    assert after["ffn_dim"] == 4 * after["hidden_size"], (
        f"expected the 4x default of {4 * after['hidden_size']}, got {after['ffn_dim']}")
    assert after["total_param_count"] != before["total_param_count"]

    _assert_only_changed(baseline["tables"], after_tables, {"doc-classifier"})


# --------------------------------------------------------------------------------------
# Layer 2b -- differential identities.
#
# These are the sharpest checks in the suite. Each perturbs one config field by a known
# amount and asserts that the parameter count moves by an EXACT quantity computed from the
# columns the export itself reports. No answer key is involved: the expected delta is a
# function of the row's own hidden_size / num_layers / head counts.
#
# An implementation that reached the right total by searching the digest, or by copying
# values, will not have the right *structure*, and structure is exactly what a derivative
# measures. Getting these right requires knowing which tensors a config's declarations
# bring into existence and how they are shaped -- which is the thing this task exists to
# measure.
# --------------------------------------------------------------------------------------

def test_gated_feed_forward_has_three_matrices(baseline, pins, perturbed):
    """Widening the feed-forward of a gated checkpoint by d must add exactly 3*L*H*d:
    a gated MLP instantiates gate, up and down. This checkpoint declares no MLP bias, so
    there is no additive bias term."""
    repo = pins["by_model"]["embedding-retriever"]["repo"]
    before = _arch_of(baseline["tables"], "embedding-retriever")
    delta = 512

    after = _arch_of(perturbed([(repo, "intermediate_size", before["ffn_dim"] + delta)]),
                     "embedding-retriever")

    expected = 3 * before["num_layers"] * before["hidden_size"] * delta
    actual = after["total_param_count"] - before["total_param_count"]
    assert actual == expected, (
        f"widening a gated feed-forward by {delta} changed the parameter count by "
        f"{actual}, not {expected} (= 3 * {before['num_layers']} layers * "
        f"{before['hidden_size']} hidden * {delta}). A gated activation instantiates "
        "three feed-forward matrices.")


def test_plain_feed_forward_has_two_matrices_and_a_bias(baseline, pins, perturbed):
    """The converse family: a non-gated feed-forward that does declare biases. Widening by
    d adds 2*L*H*d for the two matrices, plus L*d for the widened up-projection bias."""
    repo = pins["by_model"]["qa-encoder"]["repo"]
    before = _arch_of(baseline["tables"], "qa-encoder")
    delta = 512

    after = _arch_of(perturbed([(repo, "intermediate_size", before["ffn_dim"] + delta)]),
                     "qa-encoder")

    layers, hidden = before["num_layers"], before["hidden_size"]
    expected = 2 * layers * hidden * delta + layers * delta
    actual = after["total_param_count"] - before["total_param_count"]
    assert actual == expected, (
        f"widening a non-gated feed-forward by {delta} changed the parameter count by "
        f"{actual}, not {expected} (= 2 * {layers} * {hidden} * {delta} for the two "
        f"matrices, + {layers} * {delta} for the bias that widened with them)")


def test_attention_bias_is_sized_by_projection_output(baseline, pins, perturbed):
    """Turning attention biases on adds one bias per projection, each sized by that
    projection's OUTPUT width -- so the K and V biases are key-value sized, not hidden
    sized. An implementation that adds 4*H per layer fails on any grouped-query model."""
    repo = pins["by_model"]["doc-classifier"]["repo"]
    before = _arch_of(baseline["tables"], "doc-classifier")
    assert before["num_kv_heads"] < before["num_heads"], (
        "fixture precondition: this check is only meaningful on a grouped-query model")

    after = _arch_of(perturbed([(repo, "attention_bias", True)]), "doc-classifier")

    layers = before["num_layers"]
    expected = layers * (before["num_heads"] * before["head_dim"]
                         + 2 * before["num_kv_heads"] * before["head_dim"]
                         + before["hidden_size"])
    actual = after["total_param_count"] - before["total_param_count"]
    assert actual == expected, (
        f"enabling attention biases added {actual} parameters, not {expected}. Each "
        "projection gets one bias sized by its own output width: the query and output "
        "biases span the full projection, the key and value biases only the key-value "
        "width.")


def test_learned_positions_are_counted_and_rotary_are_not(baseline, pins, perturbed):
    """A learned absolute position table is a parameter matrix of P x H, so extending the
    context adds exactly d*H. A rotary checkpoint's position table is a buffer, so the
    same perturbation adds nothing at all."""
    learned_repo = pins["by_model"]["qa-encoder"]["repo"]
    learned_before = _arch_of(baseline["tables"], "qa-encoder")
    delta = 256

    learned_cfg = _load_config(pins["by_model"]["qa-encoder"])
    learned_after = _arch_of(
        perturbed([(learned_repo, "max_position_embeddings",
                    learned_cfg["max_position_embeddings"] + delta)]), "qa-encoder")
    expected = delta * learned_before["hidden_size"]
    actual = learned_after["total_param_count"] - learned_before["total_param_count"]
    assert actual == expected, (
        f"extending a learned absolute position table by {delta} added {actual} "
        f"parameters, not {expected} (= {delta} * {learned_before['hidden_size']})")

    rotary_repo = pins["by_model"]["embedding-retriever"]["repo"]
    rotary_before = _arch_of(baseline["tables"], "embedding-retriever")
    rotary_cfg = _load_config(pins["by_model"]["embedding-retriever"])
    rotary_after = _arch_of(
        perturbed([(rotary_repo, "max_position_embeddings",
                    rotary_cfg["max_position_embeddings"] + 4096)]), "embedding-retriever")
    assert rotary_after["total_param_count"] == rotary_before["total_param_count"], (
        "extending the context of a rotary checkpoint changed its parameter count; "
        "rotary position tables are buffers, not parameters")


def test_vocabulary_counts_once_when_tied_and_twice_when_not(baseline, pins, perturbed):
    """The tied/untied twins differ only in tie_word_embeddings. Growing the vocabulary by
    d must add d*H to the tied checkpoint (embeddings only) and 2*d*H to the untied one
    (embeddings plus a separate output head)."""
    delta = 1024
    for model, multiplier in (("doc-classifier", 2), ("doc-classifier-lite", 1)):
        repo = pins["by_model"][model]["repo"]
        before = _arch_of(baseline["tables"], model)
        config = _load_config(pins["by_model"][model])

        after = _arch_of(
            perturbed([(repo, "vocab_size", config["vocab_size"] + delta)]), model)

        expected = multiplier * delta * before["hidden_size"]
        actual = after["total_param_count"] - before["total_param_count"]
        assert actual == expected, (
            f"{model}: growing the vocabulary by {delta} added {actual} parameters, not "
            f"{expected} (= {multiplier} * {delta} * {before['hidden_size']}). A tied "
            "head reuses the embedding matrix; an untied head is a second matrix.")


def test_one_more_expert_adds_one_bank_and_one_router_row(baseline, pins, perturbed):
    """Adding a single expert at a fixed routing width adds one expert's feed-forward plus
    one row of the router, per layer -- and the router row alone is what active gains,
    because a token traverses the router but not the new expert."""
    repo = pins["by_model"]["chat-assistant"]["repo"]

    few = _arch_of(perturbed([(repo, "num_local_experts", 4),
                              (repo, "num_experts_per_tok", 2)]), "chat-assistant")
    more = _arch_of(perturbed([(repo, "num_local_experts", 5),
                               (repo, "num_experts_per_tok", 2)]), "chat-assistant")

    layers, hidden, ffn = few["num_layers"], few["hidden_size"], few["ffn_dim"]
    one_expert = 3 * hidden * ffn
    expected_total = layers * (one_expert + hidden)
    actual_total = more["total_param_count"] - few["total_param_count"]
    assert actual_total == expected_total, (
        f"adding one expert added {actual_total} parameters, not {expected_total} "
        f"(= {layers} layers * (one gated expert of width {ffn}, plus one router row of "
        f"width {hidden}))")

    expected_active = layers * hidden
    actual_active = more["active_param_count"] - few["active_param_count"]
    assert actual_active == expected_active, (
        f"adding one expert changed the active count by {actual_active}, not "
        f"{expected_active}. At a fixed routing width a token still traverses the same "
        "number of experts -- but the router it passes through got one row wider.")


def test_depth_is_exactly_one_block_per_layer(baseline, pins, perturbed):
    """Parameter count must be exactly affine in depth: every added layer contributes an
    identical block. Catches per-layer terms that are miscounted once rather than per
    layer, and depth-independent terms that are wrongly multiplied by depth."""
    repo = pins["by_model"]["qa-encoder"]["repo"]
    before = _arch_of(baseline["tables"], "qa-encoder")

    one = _arch_of(perturbed([(repo, "num_hidden_layers", before["num_layers"] + 1)]),
                   "qa-encoder")
    five = _arch_of(perturbed([(repo, "num_hidden_layers", before["num_layers"] + 5)]),
                    "qa-encoder")

    block = one["total_param_count"] - before["total_param_count"]
    assert five["total_param_count"] - before["total_param_count"] == 5 * block, (
        "adding five layers did not add five times what adding one layer added; the "
        "parameter count is not affine in depth")


def test_identical_architectures_share_one_row(baseline):
    """Deduplication: models resolving to the same architecture share a single
    model_architecture row, and every row is referenced."""
    tables = baseline["tables"]
    arch_rows = tables["model_architecture"]
    fingerprints = [r["fingerprint"] for r in arch_rows]
    assert len(fingerprints) == len(set(fingerprints)), (
        "model_architecture contains duplicate fingerprints; it is keyed by fingerprint")

    referenced = {v["hf_architecture_fingerprint"] for v in tables["model_versions"]
                  if v["hf_architecture_fingerprint"] is not None}
    orphans = set(fingerprints) - referenced
    assert not orphans, f"model_architecture rows nothing references: {sorted(orphans)}"

    versions_by_model = _versions_by_model(tables)
    in_scope = [m["name"] for m in tables["registered_models"]
                if m["framework"] == "transformers" and m["hf_repo_id"]]
    by_fingerprint: dict[str, set[str]] = {}
    for model in in_scope:
        for version in versions_by_model.get(model, []):
            by_fingerprint.setdefault(version["hf_architecture_fingerprint"], set()).add(model)
    shared = {f: m for f, m in by_fingerprint.items() if len(m) > 1}
    assert shared, (
        "no two models share an architecture row. The corpus contains models that resolve "
        "to identical architectures; they must deduplicate onto one row")


def test_perturbation_splits_a_shared_architecture(baseline, perturbed, pins):
    """Two models sharing one architecture row must separate onto distinct rows once their
    checkpoints stop agreeing -- and the untouched one must keep its original row."""
    tables = baseline["tables"]
    versions_by_model = _versions_by_model(tables)
    in_scope = [m["name"] for m in tables["registered_models"]
                if m["framework"] == "transformers" and m["hf_repo_id"]]
    groups: dict[str, list[str]] = {}
    for model in in_scope:
        fingerprint = versions_by_model[model][0]["hf_architecture_fingerprint"]
        groups.setdefault(fingerprint, []).append(model)
    pair = next((sorted(m) for m in groups.values() if len(m) > 1), None)
    assert pair, "fixture precondition: expected at least one shared architecture"
    target, untouched = pair[0], pair[1]

    before_shared = _arch_of(tables, target)
    repo = pins["by_model"][target]["repo"]
    after_tables = perturbed([(repo, "num_hidden_layers", before_shared["num_layers"] + 4)])

    after_target = _arch_of(after_tables, target)
    after_untouched = _arch_of(after_tables, untouched)

    assert after_target["fingerprint"] != after_untouched["fingerprint"], (
        f"{target} and {untouched} still share a fingerprint after their checkpoints "
        "diverged")
    assert after_untouched == before_shared, (
        f"{untouched} changed when only {target}'s checkpoint was perturbed")
    assert after_target["num_layers"] == before_shared["num_layers"] + 4


# --------------------------------------------------------------------------------------
# Layer 3 -- structure, scope, lineage, protocol
# --------------------------------------------------------------------------------------

def _seed_state():
    sql = _seed_sql()
    models = {}
    for name, created, description, framework in _SEED_MODEL_ROW.findall(sql):
        models[name] = {"created_time": int(created),
                        "description": description.replace("''", "'"),
                        "framework": framework}
    versions = {}
    for name, version, run_id, parent, stage, fingerprint in _SEED_VERSION_ROW.findall(sql):
        versions[(name, int(version))] = {
            "source_run_id": run_id,
            "parent_version": None if parent == "NULL" else int(parent),
            "current_stage": stage,
            "hf_architecture_fingerprint":
                None if fingerprint == "NULL" else fingerprint.strip("'"),
        }
    return models, versions


def test_out_of_scope_models_are_untouched(baseline):
    """Models outside the migration's remit -- other frameworks -- keep the exact
    fingerprint they were seeded with, including stale values from the abandoned earlier
    backfill, and gain no resolved commit."""
    seed_models, seed_versions = _seed_state()
    tables = baseline["tables"]
    models = _models_by_name(tables)

    out_of_scope = [n for n, m in seed_models.items() if m["framework"] != "transformers"]
    assert out_of_scope, "fixture precondition: expected out-of-scope models"

    violations = []
    for row in tables["model_versions"]:
        name = row["model_name"]
        if seed_models.get(name, {}).get("framework") == "transformers":
            continue
        seeded = seed_versions.get((name, row["version"]))
        if seeded is None:
            violations.append((name, row["version"], "row not in seed"))
            continue
        if row["hf_architecture_fingerprint"] != seeded["hf_architecture_fingerprint"]:
            violations.append((name, row["version"], "fingerprint rewritten"))
    assert not violations, (
        f"rows outside the migration's scope were modified: {violations}. Scope is "
        "framework = 'transformers'; other rows must survive untouched even when the value "
        "they carry is stale.")

    for name in out_of_scope:
        assert models[name]["hf_resolved_commit"] is None, (
            f"{name} is out of scope but was given a resolved commit")


def test_in_scope_stale_fingerprints_were_replaced(baseline):
    """The abandoned backfill's values must not survive on in-scope rows."""
    seed_models, seed_versions = _seed_state()
    stale = {v["hf_architecture_fingerprint"] for (n, _), v in seed_versions.items()
             if seed_models.get(n, {}).get("framework") == "transformers"
             and v["hf_architecture_fingerprint"] is not None}
    assert stale, "fixture precondition: expected stale fingerprints on in-scope rows"

    survivors = [(v["model_name"], v["version"]) for v in baseline["tables"]["model_versions"]
                 if v["hf_architecture_fingerprint"] in stale]
    assert not survivors, (
        f"stale fingerprints from the abandoned backfill survived on {survivors}")


def test_every_in_scope_model_is_fully_resolved(baseline, pins):
    """No in-scope model may be left unresolved, and no unresolvable column may be null.

    Reports which (model, column) pairs are outstanding -- not what they should contain.
    """
    tables = baseline["tables"]
    models = _models_by_name(tables)
    required = ("architecture", "model_type", "hidden_size", "num_layers", "num_heads",
                "num_kv_heads", "head_dim", "ffn_dim", "attention_variant",
                "total_param_count", "active_param_count", "kv_cache_bytes_per_token")

    outstanding = []
    for pin in pins["in_scope"]:
        name = pin["model"]
        assert models[name]["hf_resolved_commit"], f"{name}: no resolved commit recorded"
        try:
            arch = _arch_of(tables, name)
        except AssertionError as e:
            outstanding.append((name, str(e)))
            continue
        for column in required:
            if arch.get(column) is None:
                outstanding.append((name, column))
    assert not outstanding, f"unresolved after backfill: {outstanding}"


def test_tag_was_resolved_to_a_commit(baseline, pins):
    """hf_revision is a tag; the migration must resolve it through the revision API and
    fetch the config at the resulting commit, not at the tag."""
    models = _models_by_name(baseline["tables"])
    fetched = baseline["fetched"]

    for pin in pins["in_scope"]:
        name, repo, tag, sha = pin["model"], pin["repo"], pin["tag"], pin["sha"]
        recorded = models[name]["hf_resolved_commit"]
        assert recorded == sha, (
            f"{name}: hf_resolved_commit is {recorded!r}; the revision API resolves "
            f"{tag!r} to a different commit")
        assert pin["revision_url"] in fetched, (
            f"{name}: the revision API was never called for {repo}@{tag}")
        assert pin["config_url"] in fetched, (
            f"{name}: config.json was not fetched at the resolved commit")
        tag_url = f"https://huggingface.co/{repo}/resolve/{tag}/config.json"
        assert tag_url not in fetched, (
            f"{name}: config.json was fetched at the tag rather than the resolved commit")


def test_out_of_scope_checkpoints_are_not_fetched(baseline, pins):
    """Models outside the migration's scope must not be fetched at all. Two out-of-scope
    models carry perfectly valid pins; resolving them is wasted work against the Hub and
    means the scope filter is not being applied before fetching."""
    allowed = set()
    for pin in pins["in_scope"]:
        allowed.add(pin["revision_url"])
        allowed.add(pin["config_url"])
    stray = sorted(baseline["fetched"] - allowed)
    assert not stray, f"fetched checkpoints outside the migration's scope: {stray}"


def test_lineage_and_row_set_preserved(baseline):
    """Version lineage is untouched and no rows are added or dropped."""
    _seed_models, seed_versions = _seed_state()
    versions = baseline["tables"]["model_versions"]
    assert seed_versions, "could not parse lineage out of the seed SQL"

    broken = []
    for row in versions:
        key = (row["model_name"], row["version"])
        seeded = seed_versions.get(key)
        if seeded is None:
            broken.append((key, "row not present in seed"))
            continue
        for column in ("source_run_id", "parent_version", "current_stage"):
            if row[column] != seeded[column]:
                broken.append((key, column))
    assert not broken, f"lineage altered by the backfill: {broken}"
    assert len(versions) == len(seed_versions), (
        f"expected {len(seed_versions)} version rows, got {len(versions)}")


def test_canonical_export_order(baseline):
    """Fixed table order, primary-key row order within each table."""
    tables = baseline["tables"]
    order = tables["_order"]
    expected_order = ["registered_models", "model_architecture", "model_versions"]
    seen = [t for i, t in enumerate(order) if i == 0 or order[i - 1] != t]
    assert seen == [t for t in expected_order if t in seen], (
        f"canonical table order violated: tables appear as {seen}")

    names = [r["name"] for r in tables["registered_models"]]
    assert names == sorted(names), "registered_models not sorted by name"
    fingerprints = [r["fingerprint"] for r in tables["model_architecture"]]
    assert fingerprints == sorted(fingerprints), "model_architecture not sorted by fingerprint"
    keys = [(v["model_name"], v["version"]) for v in tables["model_versions"]]
    assert keys == sorted(keys), "model_versions not sorted by (model_name, version)"


def _strip_lua_comments(source: str) -> str:
    """Remove Lua comments and string literals, so a substring scan reflects code rather
    than prose. Without this, a migration that does nothing but mention the helper names
    in a comment satisfies the scan."""
    out, i, n = [], 0, len(source)
    while i < n:
        if source.startswith("--[[", i):
            end = source.find("]]", i + 4)
            i = n if end < 0 else end + 2
        elif source.startswith("--", i):
            end = source.find("\n", i)
            i = n if end < 0 else end
        elif source.startswith("[[", i):
            end = source.find("]]", i + 2)
            out.append(source[i:n if end < 0 else end + 2])
            i = n if end < 0 else end + 2
        elif source[i] in "\"'":
            quote, i = source[i], i + 1
            while i < n and source[i] != quote:
                i += 2 if source[i] == "\\" else 1
            i += 1
            out.append('""')
        else:
            out.append(source[i])
            i += 1
    return "".join(out)


def test_only_the_expected_migrations_exist():
    """The backfill belongs in V003. The runner replays every VNNN_*.lua it finds and
    re-applies everything from V003 up, so an additional migration file would be replayed
    identically -- moving the graded work out of the file under review."""
    present = sorted(p.name for p in (HARNESS_DIR / "migrations").glob("*.lua"))
    assert present == [
        "V001_add_hf_pin_columns.lua",
        "V002_add_version_metadata_columns.lua",
        "V003_backfill_hf_model_metadata.lua",
    ], f"unexpected migration files present: {present}"


def test_v003_is_what_produces_the_backfill(baseline):
    """Causal, not syntactic: with V003 emptied the export must lose its architecture
    rows. If it does not, the backfill is being produced somewhere else."""
    saved = V003_PATH.read_bytes()
    try:
        V003_PATH.write_text("-- temporarily disabled by the verifier\n", encoding="utf-8")
        _, tables = _run_harness()
        assert not tables["model_architecture"], (
            "the export still contains model_architecture rows with V003 disabled, so "
            "V003 is not what produces the backfill")
    finally:
        V003_PATH.write_bytes(saved)
        _run_harness()  # restore the graded state


def test_uses_provided_apis_only():
    """The migration reaches the database and the Hub only through the provided helpers."""
    assert V003_PATH.is_file(), f"migration not found: {V003_PATH}"
    source = _strip_lua_comments(V003_PATH.read_text(encoding="utf-8"))

    forbidden = [
        "io.open", "io.read", "io.lines", "io.popen", "io.input", "io.write",
        "os.execute", "os.getenv", "os.remove", "os.rename", "os.tmpname", "popen",
        "dofile", "loadfile", "require", "package.", "luasql", "socket.", "luajava",
        "127.0.0.1", "localhost", "8743", "/control/", "registry_seed",
        ".mv.db", "target/bundle",
    ]
    offenders = [token for token in forbidden if token in source]
    assert not offenders, (
        f"V003 bypasses the provided helpers or reads harness internals via: {offenders}")

    assert "db." in source, "V003 does not use the provided db helper"
    assert "http.get" in source, "V003 does not use the provided http.get helper"
    assert "crypto.sha256" in source, "V003 does not use the provided crypto.sha256 helper"


def test_verifier_environment_is_not_shadowed():
    """The grading process must be running the interpreter and plugins the image shipped.
    User site-packages is writable by the account these tests run as, and a plugin, .pth
    or usercustomize planted there executes inside this process."""
    import site

    import _pytest.config

    assert not site.ENABLE_USER_SITE, (
        "user site-packages is enabled in the grading process")
    assert not os.environ.get("PYTHONPATH"), "PYTHONPATH is set in the grading process"

    loaded = {d.project_name for d in
              _pytest.config.get_plugin_manager().list_plugin_distinfo()}
    unexpected = loaded - {"pytest-json-ctrf"}
    assert not unexpected, f"unexpected pytest plugins loaded: {sorted(unexpected)}"

    assert hashlib.sha256(b"").hexdigest() == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"), (
        "hashlib.sha256 does not produce the standard digest")


def test_project_junit_suite_passes():
    """The project's own end-to-end suite passes."""
    result = subprocess.run(_MVN_TEST, cwd=str(HARNESS_DIR), capture_output=True,
                            text=True, timeout=600, check=False)
    assert result.returncode == 0, (
        f"project JUnit suite still failing:\n{result.stdout}\n{result.stderr}")
