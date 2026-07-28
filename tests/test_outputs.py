"""Behavioral verification for marked Hawkes policy certificates."""

from __future__ import annotations

import csv
import gzip
import json
import math
import os
import random
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path("/tmp/retail-hawkes-verifier")
FIXTURES = {
    "public": Path("/app/data"),
    "hidden-a": Path("/tests/fixtures/hidden-a"),
    "hidden-b": Path("/tests/fixtures/hidden-b"),
}
SANDBOX = ("/usr/bin/python3", "/tests/landlock_exec.py")
CANDIDATE_UID = 65534
CANDIDATE_GID = 65534
SCHEMA = [
    "case_id",
    "selected_portfolio",
    "feasible_count",
    "robust_value",
    "full_value",
    "branching_radius",
    "worst_deletion_radius",
    "worst_pair_radius",
    "effective_sample_size",
    "pair_effective_sample_size",
    "jackknife_instability",
    "second_order_instability",
    "policy_dispersion",
    "mixture_concentration",
    "deletion_code",
    "pair_deletion_code",
    "audit_signature",
]
FLOAT_COLUMNS = {
    "robust_value",
    "full_value",
    "branching_radius",
    "worst_deletion_radius",
    "worst_pair_radius",
    "effective_sample_size",
    "pair_effective_sample_size",
    "jackknife_instability",
    "second_order_instability",
    "policy_dispersion",
    "mixture_concentration",
}
OBSERVED: dict[str, list[dict[str, str]]] = {}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(
    path: Path,
    rows: list[dict[str, str]],
    fieldnames: list[str] | None = None,
) -> None:
    columns = fieldnames or list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sealed(label: str) -> list[dict[str, str | float]]:
    with gzip.open(
        Path("/tests/sealed") / f"{label}.json.gz",
        "rt",
        encoding="utf-8",
    ) as handle:
        value = json.load(handle)
    assert isinstance(value, list)
    assert len(value) == 24
    return value


def candidate_access(path: Path) -> None:
    for current, directories, files in os.walk(path):
        os.chown(current, CANDIDATE_UID, CANDIDATE_GID)
        os.chmod(current, 0o700)
        for directory in directories:
            child = Path(current, directory)
            os.chown(child, CANDIDATE_UID, CANDIDATE_GID)
            os.chmod(child, 0o700)
        for filename in files:
            child = Path(current, filename)
            os.chown(child, CANDIDATE_UID, CANDIDATE_GID)
            os.chmod(child, 0o600)


def sandbox_run(
    run_root: Path,
    command: list[str],
    extra_writes: tuple[Path, ...] = (),
) -> subprocess.CompletedProcess[str]:
    home = run_root / "home"
    home.mkdir(mode=0o700, exist_ok=True)
    candidate_access(run_root)
    environment = os.environ.copy()
    environment.update({"HOME": str(home), "TMPDIR": str(home)})
    write_flags = [
        item for path in (run_root, *extra_writes) for item in ("--write", str(path))
    ]
    return subprocess.run(
        [*SANDBOX, *write_flags, "--", *command],
        cwd="/tmp",
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=300,
    )


def compare_rows(
    actual: list[dict[str, str]],
    target: list[dict[str, str | float]],
) -> None:
    assert actual
    assert list(actual[0]) == SCHEMA
    assert len(actual) == len(target)
    for actual_row, target_row in zip(actual, target, strict=True):
        assert set(actual_row) == set(target_row)
        for column in SCHEMA:
            if column in FLOAT_COLUMNS:
                observed = float(actual_row[column])
                reference = float(target_row[column])
                assert math.isfinite(observed)
                assert math.isclose(
                    observed,
                    reference,
                    rel_tol=2e-6,
                    abs_tol=2e-6,
                ), (actual_row["case_id"], column, observed, reference)
            else:
                assert actual_row[column] == str(target_row[column])


def run_bundle(
    label: str,
    source: Path,
    expected_label: str,
    mutate=None,
    expect_success: bool = True,
    stale_output: bytes | None = None,
) -> tuple[list[dict[str, str]], Path, subprocess.CompletedProcess[str]]:
    run_root = ROOT / label
    if run_root.exists():
        shutil.rmtree(run_root)
    run_root.mkdir(mode=0o700)
    data_root = run_root / "input"
    shutil.copytree(source, data_root)
    if mutate:
        mutate(data_root)
    output = run_root / "results.csv"
    if stale_output is not None:
        output.write_bytes(stale_output)
    completed = sandbox_run(
        run_root,
        ["/app/run.sh", str(data_root), str(output)],
    )
    if not expect_success:
        return [], output, completed
    assert completed.returncode == 0, completed.stderr
    assert output.exists()
    result = read_csv(output)
    compare_rows(result, sealed(expected_label))
    return result, output, completed


def observed_profile(label: str) -> list[dict[str, str]]:
    if label not in OBSERVED:
        rows, _, _ = run_bundle(label, FIXTURES[label], label)
        OBSERVED[label] = rows
    return OBSERVED[label]


@pytest.fixture(scope="session", autouse=True)
def clean_workspace():
    """Reset scratch space and prove verifier references are candidate-invisible."""
    if ROOT.exists():
        shutil.rmtree(ROOT)
    ROOT.mkdir(parents=True, mode=0o700)
    os.chown(ROOT, CANDIDATE_UID, CANDIDATE_GID)
    probe = ROOT / "reference-probe"
    probe.mkdir(mode=0o700)
    protected = [
        "/tests/test_outputs.py",
        "/tests/sealed/public.json.gz",
        "/tests/fixtures/hidden-a/cases.csv",
        "/solution/estimate.R",
    ]
    shell = " ".join(f'"{path}"' for path in protected)
    command = (
        f"for path in {shell}; do "
        'if head -c 1 "$path" >/dev/null 2>&1; then exit 41; fi; '
        "done"
    )
    completed = sandbox_run(probe, ["/bin/sh", "-c", command])
    assert completed.returncode == 0, completed.stderr


def test_candidate_reference_isolation(clean_workspace):
    """Prevent candidates from reading tests, sealed results, or solution files."""
    assert clean_workspace is None


@pytest.mark.parametrize("profile", ["public", "hidden-a", "hidden-b"])
@pytest.mark.parametrize("case_number", range(24))
def test_semantic_case(profile: str, case_number: int):
    """Check every field of each independent public and hidden semantic case."""
    actual = observed_profile(profile)
    target = sealed(profile)
    compare_rows([actual[case_number]], [target[case_number]])


def permute_rows_and_columns(data_root: Path) -> None:
    rows = read_csv(data_root / "records.csv")
    random.Random(736_291).shuffle(rows)
    write_csv(data_root / "records.csv", rows, list(reversed(rows[0])))


def translate_time_and_cluster(data_root: Path) -> None:
    rows = read_csv(data_root / "records.csv")
    cluster_map = {"0": "83", "1": "11", "2": "47", "3": "29"}
    for row in rows:
        row["cluster"] = cluster_map[row["cluster"]]
        row["t"] = str(int(row["t"]) + 1009)
    write_csv(data_root / "records.csv", rows)


def scale_time_decay_and_horizon(data_root: Path) -> None:
    records = read_csv(data_root / "records.csv")
    for row in records:
        row["t"] = str(2 * int(row["t"]))
    write_csv(data_root / "records.csv", records)
    cases = read_csv(data_root / "cases.csv")
    for row in cases:
        row["alpha"] = format(float(row["alpha"]) / 2, ".15g")
        row["history_horizon"] = str(2 * int(row["history_horizon"]))
    write_csv(data_root / "cases.csv", cases)


def rescale_probability_gauge(data_root: Path) -> None:
    rows = read_csv(data_root / "records.csv")
    for row in rows:
        row["target_prob"] = format(float(row["target_prob"]) * 0.5, ".15g")
        row["behavior_prob"] = format(float(row["behavior_prob"]) * 0.5, ".15g")
    write_csv(data_root / "records.csv", rows)


def translate_opaque_identifiers(data_root: Path) -> None:
    rows = read_csv(data_root / "records.csv")
    policies = {
        "P0": "kappa-7",
        "P1": "alpha-19",
        "P2": "omega-3",
        "P3": "beta-41",
    }
    clusters = {"0": "307", "1": "101", "2": "401", "3": "211"}
    for row in rows:
        row["policy_id"] = policies[row["policy_id"]]
        row["cluster"] = clusters[row["cluster"]]
        row["source_id"] = f"src-{row['source_id']}"
    write_csv(data_root / "records.csv", rows)


def scale_rewards_and_costs(data_root: Path) -> None:
    rows = read_csv(data_root / "records.csv")
    for row in rows:
        row["reward"] = format(1.7 * float(row["reward"]), ".15g")
        row["cost"] = format(1.7 * float(row["cost"]), ".15g")
    write_csv(data_root / "records.csv", rows)


def tighten_horizon_and_ridge(data_root: Path) -> None:
    cases = read_csv(data_root / "cases.csv")
    for index, row in enumerate(cases):
        row["history_horizon"] = str(1 + index % 3)
        row["ridge"] = format(0.015 + 0.005 * (index % 4), ".15g")
    write_csv(data_root / "cases.csv", cases)


def tighten_pair_constraints(data_root: Path) -> None:
    cases = read_csv(data_root / "cases.csv")
    for index, row in enumerate(cases):
        row["pair_budget"] = format(0.70 + 0.025 * (index % 5), ".15g")
        row["interaction_limit"] = format(
            0.02 + 0.015 * (index % 4),
            ".15g",
        )
    write_csv(data_root / "cases.csv", cases)


def increase_switching_excitation(data_root: Path) -> None:
    cases = read_csv(data_root / "cases.csv")
    for index, row in enumerate(cases):
        row["switch_gain"] = format(0.12 + 0.04 * (index % 5), ".15g")
        row["triple_gain"] = format(1.10 + 0.15 * (index % 5), ".15g")
    write_csv(data_root / "cases.csv", cases)


def suppress_three_way_excitation(data_root: Path) -> None:
    cases = read_csv(data_root / "cases.csv")
    for row in cases:
        row["triple_gain"] = "0"
    write_csv(data_root / "cases.csv", cases)


def tighten_portfolio_constraints(data_root: Path) -> None:
    cases = read_csv(data_root / "cases.csv")
    for index, row in enumerate(cases):
        row["max_concentration"] = format(
            0.29 + 0.02 * (index % 4),
            ".15g",
        )
        row["dispersion_limit"] = format(
            0.35 + 0.12 * (index % 5),
            ".15g",
        )
    write_csv(data_root / "cases.csv", cases)


def reorder_cases_and_records(data_root: Path) -> None:
    cases = read_csv(data_root / "cases.csv")
    random.Random(81_017).shuffle(cases)
    write_csv(data_root / "cases.csv", cases)
    records = read_csv(data_root / "records.csv")
    random.Random(81_018).shuffle(records)
    write_csv(data_root / "records.csv", records, list(reversed(records[0])))


VARIANTS = [
    ("permuted", "hidden-a", permute_rows_and_columns),
    ("translated", "hidden-a", translate_time_and_cluster),
    ("time-scale", "hidden-a", scale_time_decay_and_horizon),
    ("probability-gauge", "hidden-a", rescale_probability_gauge),
    ("opaque-labels", "hidden-b", translate_opaque_identifiers),
    ("mark-scale", "hidden-b", scale_rewards_and_costs),
    ("tight-parameters", "hidden-b", tighten_horizon_and_ridge),
    ("pair-tight", "hidden-b", tighten_pair_constraints),
    ("switch-stress", "hidden-b", increase_switching_excitation),
    ("triple-suppressed", "hidden-a", suppress_three_way_excitation),
    ("portfolio-tight", "hidden-b", tighten_portfolio_constraints),
    ("case-order", "hidden-b", reorder_cases_and_records),
]


@pytest.mark.parametrize(("label", "profile", "mutate"), VARIANTS)
@pytest.mark.parametrize("case_number", range(24))
def test_variant_semantic_case(
    label: str,
    profile: str,
    mutate,
    case_number: int,
):
    """Check refits on transformed hidden bundles against sealed references."""
    if label not in OBSERVED:
        rows, _, _ = run_bundle(label, FIXTURES[profile], label, mutate)
        OBSERVED[label] = rows
    compare_rows(
        [OBSERVED[label][case_number]],
        [sealed(label)[case_number]],
    )


def test_feasibility_boundaries_are_decision_relevant():
    """Exercise empty through all-feasible pools across independent profiles."""
    counts = {
        int(row["feasible_count"])
        for profile in FIXTURES
        for row in observed_profile(profile)
    }
    assert 0 in counts
    assert 1 in counts
    assert len(counts) >= 10
    assert max(counts) >= 20


def test_nested_certificate_shapes_cover_every_deletion_surface():
    """Require four nested single deletions and all six ordered cluster pairs."""
    for profile in FIXTURES:
        for row in observed_profile(profile):
            single_tokens = row["deletion_code"].split("|")
            pair_tokens = row["pair_deletion_code"].split("|")
            assert len(single_tokens) == 4
            assert all(len(token.split(":")) == 10 for token in single_tokens)
            assert len(pair_tokens) == 6
            assert all(len(token.split(":")) == 7 for token in pair_tokens)
            pairs = [token.split(":", 1)[0] for token in pair_tokens]
            components = [
                tuple(int(value) for value in pair.split("+")) for pair in pairs
            ]
            assert all(left < right for left, right in components)
            assert components == sorted(components)


def test_policy_cardinality_and_portfolio_units_are_data_driven():
    """Exercise both four- and five-policy integer portfolio simplexes."""
    cardinalities: set[int] = set()
    for profile, data_root in FIXTURES.items():
        records = read_csv(data_root / "records.csv")
        cases = read_csv(data_root / "cases.csv")
        actual = observed_profile(profile)
        for case, result in zip(cases, actual, strict=True):
            policies = {
                row["policy_id"]
                for row in records
                if row["case_id"] == case["case_id"]
            }
            cardinalities.add(len(policies))
            parts = result["selected_portfolio"].split("+")
            selected = {part.rsplit("@", 1)[0] for part in parts}
            units = sum(int(part.rsplit("@", 1)[1]) for part in parts)
            assert selected <= policies
            assert units == int(case["mixture_units"])
    assert cardinalities == {4, 5}


def test_pair_constraints_change_the_robust_decision_surface():
    """Prove pair risk and interaction limits affect hidden policy decisions."""
    baseline = observed_profile("hidden-b")
    if "pair-tight" not in OBSERVED:
        rows, _, _ = run_bundle(
            "pair-tight",
            FIXTURES["hidden-b"],
            "pair-tight",
            tighten_pair_constraints,
        )
        OBSERVED["pair-tight"] = rows
    transformed = OBSERVED["pair-tight"]
    changed = sum(
        actual["selected_portfolio"] != reference["selected_portfolio"]
        or actual["feasible_count"] != reference["feasible_count"]
        or not math.isclose(
            float(actual["robust_value"]),
            float(reference["robust_value"]),
            rel_tol=2e-6,
            abs_tol=2e-6,
        )
        for actual, reference in zip(transformed, baseline, strict=True)
    )
    assert changed >= 12


def test_switching_excitation_changes_portfolio_dynamics():
    """Make nonlinear cross-policy excitation decisive on hidden portfolios."""
    baseline = observed_profile("hidden-b")
    if "switch-stress" not in OBSERVED:
        rows, _, _ = run_bundle(
            "switch-stress",
            FIXTURES["hidden-b"],
            "switch-stress",
            increase_switching_excitation,
        )
        OBSERVED["switch-stress"] = rows
    transformed = OBSERVED["switch-stress"]
    changed = sum(
        actual["selected_portfolio"] != reference["selected_portfolio"]
        or not math.isclose(
            float(actual["branching_radius"]),
            float(reference["branching_radius"]),
            rel_tol=2e-6,
            abs_tol=2e-6,
        )
        for actual, reference in zip(transformed, baseline, strict=True)
    )
    assert changed >= 18


def test_three_way_excitation_is_decision_relevant():
    """Reject pairwise-only branching on the five-policy portfolio surface."""
    baseline = observed_profile("hidden-a")
    if "triple-suppressed" not in OBSERVED:
        rows, _, _ = run_bundle(
            "triple-suppressed",
            FIXTURES["hidden-a"],
            "triple-suppressed",
            suppress_three_way_excitation,
        )
        OBSERVED["triple-suppressed"] = rows
    transformed = OBSERVED["triple-suppressed"]
    changed = sum(
        actual["selected_portfolio"] != reference["selected_portfolio"]
        or not math.isclose(
            float(actual["full_value"]),
            float(reference["full_value"]),
            rel_tol=0,
            abs_tol=1e-8,
        )
        for actual, reference in zip(baseline, transformed, strict=True)
    )
    assert changed >= 12


def test_portfolio_constraints_change_feasible_search():
    """Make concentration and fitted-policy dispersion decision relevant."""
    baseline = observed_profile("hidden-b")
    if "portfolio-tight" not in OBSERVED:
        rows, _, _ = run_bundle(
            "portfolio-tight",
            FIXTURES["hidden-b"],
            "portfolio-tight",
            tighten_portfolio_constraints,
        )
        OBSERVED["portfolio-tight"] = rows
    transformed = OBSERVED["portfolio-tight"]
    changed = sum(
        actual["selected_portfolio"] != reference["selected_portfolio"]
        or actual["feasible_count"] != reference["feasible_count"]
        for actual, reference in zip(transformed, baseline, strict=True)
    )
    assert changed >= 12


def test_invariant_surfaces_preserve_exact_certificate():
    """Require irrelevant gauges to preserve decisions and tolerated numerics."""
    baseline = observed_profile("hidden-a")
    invariants = {
        "permuted": permute_rows_and_columns,
        "time-scale": scale_time_decay_and_horizon,
        "probability-gauge": rescale_probability_gauge,
    }
    for label, mutate in invariants.items():
        if label not in OBSERVED:
            rows, _, _ = run_bundle(
                label,
                FIXTURES["hidden-a"],
                label,
                mutate,
            )
            OBSERVED[label] = rows
        transformed = OBSERVED[label]
        compare_rows(transformed, sealed("hidden-a"))
        for actual, reference in zip(transformed, baseline, strict=True):
            for column in set(SCHEMA) - FLOAT_COLUMNS:
                assert actual[column] == reference[column]


def test_destination_replacement_and_byte_determinism():
    """Replace stale output and emit byte-identical repeated certificates."""
    run_root = ROOT / "determinism"
    if run_root.exists():
        shutil.rmtree(run_root)
    run_root.mkdir(mode=0o700)
    data_root = run_root / "input"
    shutil.copytree(FIXTURES["hidden-b"], data_root)
    output = run_root / "results.csv"
    output.write_text("stale-tail\n" * 20, encoding="utf-8")
    first_run = sandbox_run(
        run_root,
        ["/app/run.sh", str(data_root), str(output)],
    )
    assert first_run.returncode == 0, first_run.stderr
    first = output.read_bytes()
    second_run = sandbox_run(
        run_root,
        ["/app/run.sh", str(data_root), str(output)],
    )
    assert second_run.returncode == 0, second_run.stderr
    second = output.read_bytes()
    assert first == second
    assert b"stale-tail" not in second
    compare_rows(read_csv(output), sealed("hidden-b"))


def invalid_duplicate_event(data_root: Path) -> None:
    rows = read_csv(data_root / "records.csv")
    rows.append(dict(rows[0]))
    write_csv(data_root / "records.csv", rows)


def invalid_probability(data_root: Path) -> None:
    rows = read_csv(data_root / "records.csv")
    rows[0]["behavior_prob"] = "0"
    write_csv(data_root / "records.csv", rows)


def invalid_missing_header(data_root: Path) -> None:
    rows = read_csv(data_root / "cases.csv")
    for row in rows:
        del row["stability_limit"]
    write_csv(data_root / "cases.csv", rows)


def invalid_ridge(data_root: Path) -> None:
    rows = read_csv(data_root / "cases.csv")
    rows[0]["ridge"] = "0"
    write_csv(data_root / "cases.csv", rows)


def invalid_horizon(data_root: Path) -> None:
    rows = read_csv(data_root / "cases.csv")
    rows[0]["history_horizon"] = "2.5"
    write_csv(data_root / "cases.csv", rows)


def invalid_policy_coverage(data_root: Path) -> None:
    rows = read_csv(data_root / "records.csv")
    case_id = rows[0]["case_id"]
    rows = [
        row
        for row in rows
        if not (
            row["case_id"] == case_id
            and row["policy_id"] == "P0"
            and row["cluster"] == "3"
        )
    ]
    write_csv(data_root / "records.csv", rows)


def invalid_group_after_deletion(data_root: Path) -> None:
    rows = read_csv(data_root / "records.csv")
    case_id = rows[0]["case_id"]
    for row in rows:
        if (
            row["case_id"] == case_id
            and row["policy_id"] == "P0"
            and row["cluster"] != "0"
        ):
            row["group"] = "0"
    write_csv(data_root / "records.csv", rows)


def invalid_case_relation(data_root: Path) -> None:
    rows = read_csv(data_root / "records.csv")
    rows[0]["case_id"] = "orphan-case"
    write_csv(data_root / "records.csv", rows)


def invalid_nonfinite(data_root: Path) -> None:
    rows = read_csv(data_root / "records.csv")
    rows[0]["reward"] = "NaN"
    write_csv(data_root / "records.csv", rows)


def invalid_identifier(data_root: Path) -> None:
    rows = read_csv(data_root / "records.csv")
    rows[0]["policy_id"] = "policé"
    write_csv(data_root / "records.csv", rows)


def invalid_pair_budget(data_root: Path) -> None:
    rows = read_csv(data_root / "cases.csv")
    rows[0]["pair_budget"] = "-0.1"
    write_csv(data_root / "cases.csv", rows)


def invalid_budget(data_root: Path) -> None:
    rows = read_csv(data_root / "cases.csv")
    rows[0]["budget"] = "-0.1"
    write_csv(data_root / "cases.csv", rows)


def invalid_interaction_limit(data_root: Path) -> None:
    rows = read_csv(data_root / "cases.csv")
    rows[0]["interaction_limit"] = "-0.1"
    write_csv(data_root / "cases.csv", rows)


def invalid_switch_gain(data_root: Path) -> None:
    rows = read_csv(data_root / "cases.csv")
    rows[0]["switch_gain"] = "-0.1"
    write_csv(data_root / "cases.csv", rows)


def invalid_triple_gain(data_root: Path) -> None:
    rows = read_csv(data_root / "cases.csv")
    rows[0]["triple_gain"] = "-0.1"
    write_csv(data_root / "cases.csv", rows)


def invalid_dispersion_penalty(data_root: Path) -> None:
    rows = read_csv(data_root / "cases.csv")
    rows[0]["dispersion_penalty"] = "-0.1"
    write_csv(data_root / "cases.csv", rows)


def invalid_dispersion_limit(data_root: Path) -> None:
    rows = read_csv(data_root / "cases.csv")
    rows[0]["dispersion_limit"] = "-0.1"
    write_csv(data_root / "cases.csv", rows)


def invalid_concentration(data_root: Path) -> None:
    rows = read_csv(data_root / "cases.csv")
    rows[0]["max_concentration"] = "0.2"
    write_csv(data_root / "cases.csv", rows)


def invalid_mixture_units(data_root: Path) -> None:
    rows = read_csv(data_root / "cases.csv")
    rows[0]["mixture_units"] = "6.5"
    write_csv(data_root / "cases.csv", rows)


def invalid_policy_count(data_root: Path) -> None:
    rows = read_csv(data_root / "records.csv")
    case_id = rows[0]["case_id"]
    rows = [
        row
        for row in rows
        if not (row["case_id"] == case_id and row["policy_id"] == "P3")
    ]
    write_csv(data_root / "records.csv", rows)


def invalid_excess_policy_count(data_root: Path) -> None:
    rows = read_csv(data_root / "records.csv")
    case_id = rows[0]["case_id"]
    source = [
        row
        for row in rows
        if row["case_id"] == case_id and row["policy_id"] == "P3"
    ]
    additions = []
    for policy_id in ("P4", "P5"):
        for row in source:
            clone = dict(row)
            clone["policy_id"] = policy_id
            additions.append(clone)
    write_csv(data_root / "records.csv", [*rows, *additions])


def invalid_pair_group_after_deletion(data_root: Path) -> None:
    rows = read_csv(data_root / "records.csv")
    case_id = rows[0]["case_id"]
    for row in rows:
        if (
            row["case_id"] == case_id
            and row["policy_id"] == "P0"
            and row["cluster"] in {"0", "1"}
        ):
            row["group"] = "0"
    write_csv(data_root / "records.csv", rows)


@pytest.mark.parametrize(
    ("label", "mutate"),
    [
        ("duplicate-event", invalid_duplicate_event),
        ("zero-probability", invalid_probability),
        ("missing-header", invalid_missing_header),
        ("zero-ridge", invalid_ridge),
        ("fractional-horizon", invalid_horizon),
        ("policy-coverage", invalid_policy_coverage),
        ("group-after-deletion", invalid_group_after_deletion),
        ("case-relation", invalid_case_relation),
        ("nonfinite", invalid_nonfinite),
        ("identifier", invalid_identifier),
        ("negative-budget", invalid_budget),
        ("negative-pair-budget", invalid_pair_budget),
        ("negative-interaction-limit", invalid_interaction_limit),
        ("negative-switch-gain", invalid_switch_gain),
        ("negative-triple-gain", invalid_triple_gain),
        ("negative-dispersion-penalty", invalid_dispersion_penalty),
        ("negative-dispersion-limit", invalid_dispersion_limit),
        ("low-concentration", invalid_concentration),
        ("fractional-mixture-units", invalid_mixture_units),
        ("policy-count", invalid_policy_count),
        ("excess-policy-count", invalid_excess_policy_count),
        ("pair-group-after-deletion", invalid_pair_group_after_deletion),
    ],
)
def test_malformed_bundle_is_rejected_without_replacing_output(label, mutate):
    """Reject each documented contract violation and preserve prior output."""
    sentinel = f"do-not-replace-{label}\n".encode()
    _, output, completed = run_bundle(
        f"invalid-{label}",
        FIXTURES["public"],
        "public",
        mutate,
        expect_success=False,
        stale_output=sentinel,
    )
    assert completed.returncode != 0
    assert output.read_bytes() == sentinel


def test_documented_default_paths():
    """Honor the documented no-argument data and destination paths."""
    run_root = ROOT / "defaults"
    if run_root.exists():
        shutil.rmtree(run_root)
    run_root.mkdir(mode=0o700)
    output_root = Path("/app/outputs")
    output_root.mkdir(parents=True, exist_ok=True)
    os.chown(output_root, CANDIDATE_UID, CANDIDATE_GID)
    os.chmod(output_root, 0o700)
    output = output_root / "results.csv"
    output.unlink(missing_ok=True)
    completed = sandbox_run(
        run_root,
        ["/app/run.sh"],
        extra_writes=(output_root,),
    )
    assert completed.returncode == 0, completed.stderr
    compare_rows(read_csv(output), sealed("public"))
