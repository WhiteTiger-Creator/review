"""Acceptance tests for the `slate resolve` planner.

Grading stands on four legs: expected selections for the shipped project
library, invariants each artifact must satisfy on its own (every digest is
recomputed from the payload the planner published, and cross-checked against the
row the ladder carries), a holdout registry that never ships in the agent image,
and edits to the inputs that must move the answer. A planner that recites the
shipped projects, or that hashes the serialised artifact instead of the payload,
fails at least one leg.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

BIN = "/app/bin/slate"
APP_OUT = Path("/app/out")
REGISTRY = Path("/app/registry")
MANIFESTS = Path("/app/manifests")

HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
PROTOCOL = "slate/1"

# Expected resolutions for the shipped projects, worked out from the contracts
# under /app/docs. Keys are the lock keys the schema names.
EXPECTED = {
    "brackenfield": {
        "packages": {
            "basalt": "2.2.4",
            "chert": "1.3.0",
            "dolomite": "2.8.0",
            "gabbro": "4.1.1",
            "marl": "2.1.0",
            "quartz": "2.2.0",
            "schist": "5.0.1",
        },
        "waived": ["schist@5.0.1 requires dolomite ^3.0.0"],
        "stats": {"assignments": 7, "backtracks": 1},
        "allow_yanked": False,
    },
    "crucible": {
        "packages": {"flint": "1.0.0-rc.2", "gneiss": "1.1.0"},
        "waived": [],
        "stats": {"assignments": 2, "backtracks": 0},
        "allow_yanked": False,
    },
    "driftworks": {
        "packages": {"gneiss": "1.2.0"},
        "waived": [],
        "stats": {"assignments": 1, "backtracks": 0},
        "allow_yanked": True,
    },
    "foundry": {
        "packages": {
            "basalt": "2.3.0",
            "chert": "1.5.0",
            "dolomite": "3.1.0",
            "flint": "0.9.3",
            "gabbro": "4.2.0",
            "gneiss": "1.1.0",
            "marl": "2.1.0",
            "quartz": "2.2.0",
            "schist": "5.0.1",
        },
        "waived": [],
        "stats": {"assignments": 9, "backtracks": 0},
        "allow_yanked": False,
    },
    "kilnworks": {
        "packages": {
            "basalt": "2.3.0",
            "chert": "1.5.0",
            "dolomite": "3.1.0",
            "quartz": "2.2.0",
            "tuff": "0.4.3",
        },
        "waived": [],
        "stats": {"assignments": 5, "backtracks": 0},
        "allow_yanked": False,
    },
    "rampart": {
        "packages": {
            "basalt": "1.9.0",
            "gabbro": "4.2.0",
            "marl": "2.1.0",
            "quartz": "2.2.0",
        },
        "waived": ["gabbro@4.2.0 requires basalt ^2.3.0"],
        "stats": {"assignments": 4, "backtracks": 0},
        "allow_yanked": False,
    },
    "slagworks": {
        "packages": {"gabbro": "4.0.0", "marl": "1.8.2", "quartz": "1.9.4"},
        "waived": [],
        "stats": {"assignments": 3, "backtracks": 2},
        "allow_yanked": False,
    },
}

# Package, chosen version, and the candidate list the picker was iterating.
WALKS = {
    "brackenfield": [
        ("schist", "5.0.1", ["5.0.1"]),
        ("dolomite", "2.8.0", ["2.8.0"]),
        ("chert", "1.3.0", ["1.3.0"]),
        ("basalt", "2.2.4", ["2.2.4"]),
        ("gabbro", "4.1.1", ["4.2.0", "4.1.1"]),
        ("marl", "2.1.0", ["2.1.0", "2.0.3"]),
        ("quartz", "2.2.0", ["2.2.0", "2.1.3"]),
    ],
    "crucible": [
        ("flint", "1.0.0-rc.2", ["1.0.0-rc.2", "1.0.0-rc.1"]),
        ("gneiss", "1.1.0", ["1.1.0"]),
    ],
    "foundry": [
        ("schist", "5.0.1", ["5.0.1"]),
        ("dolomite", "3.1.0", ["3.1.0", "3.0.2"]),
        ("chert", "1.5.0", ["1.5.0"]),
        ("basalt", "2.3.0", ["2.3.0", "2.2.4"]),
        ("flint", "0.9.3", ["0.9.3", "0.9.2"]),
        ("gabbro", "4.2.0", ["4.2.0", "4.1.1"]),
        ("gneiss", "1.1.0", ["1.1.0", "1.0.4"]),
        ("marl", "2.1.0", ["2.1.0", "2.0.3"]),
        ("quartz", "2.2.0", ["2.2.0", "2.1.3"]),
    ],
    "kilnworks": [
        ("chert", "1.5.0", ["1.5.0"]),
        ("quartz", "2.2.0", ["2.2.0"]),
        ("basalt", "2.3.0", ["2.3.0", "2.2.4"]),
        ("dolomite", "3.1.0", ["3.1.0", "3.0.2"]),
        ("tuff", "0.4.3", ["0.4.3", "0.4.1"]),
    ],
    "rampart": [
        ("gabbro", "4.2.0", ["4.2.0"]),
        ("basalt", "1.9.0", ["1.9.0"]),
        ("marl", "2.1.0", ["2.1.0", "2.0.3"]),
        ("quartz", "2.2.0", ["2.2.0", "2.1.3"]),
    ],
    "slagworks": [
        ("marl", "1.8.2", ["1.8.2"]),
        ("quartz", "1.9.4", ["1.9.4"]),
        ("gabbro", "4.0.0", ["4.2.0", "4.1.1", "4.0.0"]),
    ],
}

DEAD_END = "emberyard"
EMBERYARD_DEADLOCK = {
    "package": "quartz",
    "constraints": [
        {"requirer": "marl@1.8.2", "range": "~1.9.0"},
        {"requirer": "root", "range": "^2.2.0"},
    ],
    "backtracks": 7,
}

# Holdout library: these packages and projects are not in the agent image.
HOLDOUT = {
    "dunemoor": {
        "packages": {"dunite": "0.4.9"},
        "stats": {"assignments": 1, "backtracks": 0},
    },
    "harborline": {
        "packages": {
            "amberite": "3.0.0",
            "birchwood": "1.1.0",
            "cobalt": "1.3.0",
            "dunite": "0.5.4",
        },
        "stats": {"assignments": 4, "backtracks": 0},
    },
    "quarryhead": {
        "packages": {"cobalt": "1.3.0", "elmstone": "2.0.0-rc.3"},
        "stats": {"assignments": 2, "backtracks": 0},
    },
    "saltmarsh": {
        "packages": {"amberite": "2.4.1", "birchwood": "1.0.2", "cobalt": "1.1.4"},
        "stats": {"assignments": 3, "backtracks": 2},
        "steps": [
            ("birchwood", "1.0.2", ["1.1.0", "1.0.2"]),
            ("amberite", "2.4.1", ["2.4.1"]),
            ("cobalt", "1.1.4", ["1.1.4", "1.1.0"]),
        ],
    },
    "tidefall": {
        "packages": {"amberite": "3.0.0", "birchwood": "1.1.0", "cobalt": "1.1.0"},
        "stats": {"assignments": 3, "backtracks": 0},
        "waived": ["amberite@3.0.0 requires cobalt ^1.2.0"],
    },
}

HOLDOUT_DEADLOCK = {
    "project": "northreach",
    "package": "cobalt",
    "constraints": [
        {"requirer": "elmstone@1.6.0", "range": "~1.1.0"},
        {"requirer": "root", "range": "^1.3.0"},
    ],
    "backtracks": 2,
}


# --- helpers -----------------------------------------------------------------


def run_slate(*args):
    return subprocess.run([BIN, *args], capture_output=True, text=True)


def resolve_batch(out_dir, registry=None, manifests=None):
    args = ["resolve", "--all", "--out", str(out_dir)]
    if registry is not None:
        args += ["--registry", str(registry)]
    if manifests is not None:
        args += ["--manifests", str(manifests)]
    proc = run_slate(*args)
    assert proc.returncode == 0, f"resolve --all failed: {proc.stderr.strip()}"
    return proc


def lock_at(out_dir, project):
    return out_dir / (project + ".lock.json")


def walk_at(out_dir, project):
    return out_dir / "staging" / (project + ".trail.json")


def deadlock_at(out_dir, project):
    return out_dir / (project + ".conflict.json")


def ladder_at(out_dir):
    return out_dir / "index.json"


def load(path):
    assert path.is_file(), f"missing artifact {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def reference_fingerprint(payload_lines):
    """sha256 over a payload, as /app/docs/digest-spec.md defines it."""
    if not payload_lines:
        return hashlib.sha256(b"").hexdigest()
    payload = ("\n".join(payload_lines) + "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def reference_lock_payload(doc):
    lines = [
        "protocol\t" + PROTOCOL,
        "project\t" + doc["project"],
        "allow-yanked\t" + ("true" if doc["allow_yanked"] else "false"),
    ]
    for entry in doc["packages"]:
        lines.append(
            "pkg\t%s\t%s\t%s\t%s"
            % (
                entry["name"],
                entry["version"],
                "true" if entry["yanked"] else "false",
                ",".join(entry["features"]),
            )
        )
    for waiver in doc["waived"]:
        lines.append("waive\t" + waiver)
    return lines


def reference_walk_payload(doc):
    lines = ["protocol\t" + PROTOCOL, "trail\t" + doc["project"]]
    for entry in doc["steps"]:
        lines.append(
            "step\t%d\t%s\t%s\t%s"
            % (
                entry["step"],
                entry["package"],
                entry["version"],
                ",".join(entry["candidates"]),
            )
        )
    return lines


def reference_deadlock_payload(doc):
    lines = [
        "protocol\t" + PROTOCOL,
        "conflict\t%s\t%s" % (doc["project"], doc["package"]),
    ]
    for item in doc["constraints"]:
        lines.append("constraint\t%s\t%s" % (item["requirer"], item["range"]))
    return lines


def reference_ladder_payload(doc):
    lines = ["protocol\t" + PROTOCOL, "index\t%d" % len(doc["projects"])]
    for entry in doc["projects"]:
        lines.append(
            "project\t%s\t%s\t%d\t%d\t%s"
            % (
                entry["project"],
                entry["status"],
                entry["packages"],
                entry["backtracks"],
                entry["digest"],
            )
        )
    return lines


def selection_of(doc):
    return {entry["name"]: entry["version"] for entry in doc["packages"]}


def walk_of(doc):
    return [(s["package"], s["version"], s["candidates"]) for s in doc["steps"]]


def copy_inputs(tmp_path):
    registry = tmp_path / "registry"
    manifests = tmp_path / "manifests"
    shutil.copytree(REGISTRY, registry)
    shutil.copytree(MANIFESTS, manifests)
    return registry, manifests


@pytest.fixture(scope="module")
def published(tmp_path_factory):
    """One batch run over the shipped projects, into a scratch directory."""
    out = tmp_path_factory.mktemp("published")
    resolve_batch(out)
    return out


@pytest.fixture(scope="module")
def holdout(tmp_path_factory):
    """One batch run over the holdout library the agent image never carries."""
    fixtures = Path(os.environ["TB3_SLATE_FIXTURES"])
    out = tmp_path_factory.mktemp("holdout")
    resolve_batch(out, registry=fixtures / "registry", manifests=fixtures / "manifests")
    return out


# --- the tool that shipped still behaves ------------------------------------


def test_cli_announces_the_resolver_protocol():
    """The instruction keeps slate version and its four constant lines."""
    proc = run_slate("version")
    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.strip().splitlines()
    assert lines[0].startswith("slate ")
    assert lines[1] == "resolver-protocol " + PROTOCOL
    assert lines[2] == "digest sha256"
    assert lines[3] == "lock-schema 1"


def test_browsing_commands_answer_exactly_as_before():
    """The instruction forbids disturbing show, versions and audit."""
    listing = run_slate("versions", "basalt")
    assert listing.returncode == 0, listing.stderr
    assert listing.stdout == "2.3.1 yanked\n2.3.0\n2.2.4\n1.9.0\n"
    detail = run_slate("show", "chert")
    assert "  feature trace requires tuff ^0.4.0" in detail.stdout.splitlines()


def test_package_files_and_manifests_were_not_edited():
    """The instruction pins the registry and manifest directories as shipped."""
    totals = run_slate("audit")
    assert totals.returncode == 0, totals.stderr
    assert totals.stdout.strip() == "audit packages=10 releases=32 yanked=2"
    assert sorted(p.stem for p in MANIFESTS.iterdir()) == sorted(
        list(EXPECTED) + [DEAD_END]
    )
    chert = json.loads((REGISTRY / "chert.json").read_text(encoding="utf-8"))
    assert [rel["version"] for rel in chert["releases"]] == ["1.5.0", "1.4.2", "1.3.0"]


def test_argument_mistakes_are_told_apart_from_bad_input():
    """slate-cli.md separates exit 2 (command line) from exit 4 (inputs), and
    every exit-2 error prints the slate: line and then the usage block."""
    usage_cases = [
        ("resolve",),
        ("resolve", "foundry", "--all"),
        ("nosuchcommand",),
        ("resolve", "--nosuchflag"),
    ]
    for argv in usage_cases:
        proc = run_slate(*argv)
        assert proc.returncode == 2, argv
        assert proc.stdout == "", (argv, proc.stdout)
        lines = proc.stderr.splitlines()
        assert lines, argv
        assert lines[0].startswith("slate: "), (argv, proc.stderr)
        usage = [ln for ln in lines[1:] if ln.startswith("usage: slate")]
        assert usage, ("usage block missing", argv, proc.stderr)
        # the usage block lists the subcommands, resolve among them
        assert any(re.match(r"\s+resolve\b", ln) for ln in lines), (argv, proc.stderr)

    # exit 4 is an input error, not a command-line mistake
    assert run_slate("resolve", "nosuchproject").returncode == 4


def test_manifest_command_prints_and_exports_unchanged(tmp_path):
    """The manifest subcommand keeps printing canonical JSON and exporting it."""
    printed = run_slate("manifest", "kilnworks")
    assert printed.returncode == 0, printed.stderr
    doc = json.loads(printed.stdout)
    assert doc["protocol"] == PROTOCOL
    assert doc["project"] == "kilnworks"
    assert doc["allow_yanked"] is False
    assert [req["name"] for req in doc["requires"]] == ["dolomite", "chert", "quartz"]
    assert [req["features"] for req in doc["requires"]] == [[], ["trace"], ["simd"]]
    assert printed.stdout.endswith("}\n")
    exported = run_slate("manifest", "kilnworks", "--export", "--out", str(tmp_path))
    assert exported.returncode == 0, exported.stderr
    staged = tmp_path / "staging" / "kilnworks.manifest.json"
    assert staged.is_file()
    assert exported.stdout.strip().endswith(str(staged))
    assert json.loads(staged.read_text(encoding="utf-8")) == doc


def test_directory_overrides_accept_both_spellings_anywhere(tmp_path):
    """slate-cli.md promises --flag VALUE and --flag=VALUE, in any position."""
    registry, manifests = copy_inputs(tmp_path)
    expected = run_slate("resolve", "crucible", "--out", str(tmp_path / "baseline"))
    assert expected.returncode == 0, expected.stderr
    baseline = load(lock_at(tmp_path / "baseline", "crucible"))
    spellings = [
        ["--registry", str(registry), "--manifests", str(manifests), "resolve", "crucible"],
        ["resolve", "--registry=" + str(registry), "crucible", "--manifests=" + str(manifests)],
        ["resolve", "crucible", "--manifests", str(manifests), "--registry=" + str(registry)],
    ]
    for n, argv in enumerate(spellings):
        out = tmp_path / ("form%d" % n)
        proc = run_slate(*argv, "--out", str(out))
        assert proc.returncode == 0, " ".join(argv) + "\n" + proc.stderr
        assert load(lock_at(out, "crucible"))["digest"] == baseline["digest"], argv
    listing = run_slate("versions", "basalt", "--registry=" + str(registry))
    assert listing.returncode == 0, listing.stderr
    assert listing.stdout == run_slate("versions", "basalt").stdout


def test_input_errors_are_one_line_on_stderr(tmp_path):
    """Every error is a single stderr line prefixed slate:, with a silent stdout."""
    registry, manifests = copy_inputs(tmp_path)
    (registry / "tuff.json").unlink()
    (manifests / "brokenyard.slate").write_text(
        "project brokenyard\nrequire chert ^1.5.0\nprefer chert 1.4.2\n", encoding="utf-8"
    )
    cases = [
        ("resolve", "nosuchproject"),
        ("resolve", "kilnworks", "--registry", str(registry)),
        ("resolve", "brokenyard", "--manifests", str(manifests)),
        ("show", "nosuchpackage"),
    ]
    for argv in cases:
        proc = run_slate(*argv, "--out", str(tmp_path / "out"))
        assert proc.returncode == 4, argv
        lines = proc.stderr.strip().splitlines()
        assert len(lines) == 1, (argv, proc.stderr)
        assert lines[0].startswith("slate: "), (argv, proc.stderr)
        assert proc.stdout == "", (argv, proc.stdout)


def test_a_refused_batch_leaves_the_output_directory_alone(tmp_path):
    """A batch that cannot read an input publishes nothing, not half a library."""
    registry, manifests = copy_inputs(tmp_path)
    # Sorts after every shipped project, so a resolver that publishes as it goes
    # has already written most of the library by the time it reads this one.
    project = "wrongyard"
    (manifests / (project + ".slate")).write_text(
        "project wrongyard\nrequire chert ^1.5.0\nprefer chert 1.4.2\n", encoding="utf-8"
    )
    out = tmp_path / "out"
    out.mkdir()
    proc = run_slate(
        "resolve", "--all", "--registry", str(registry),
        "--manifests", str(manifests), "--out", str(out),
    )
    assert proc.returncode == 4, proc.stdout + proc.stderr
    assert list(out.iterdir()) == [], sorted(p.name for p in out.iterdir())
    single = run_slate(
        "resolve", project, "--registry", str(registry),
        "--manifests", str(manifests), "--out", str(out),
    )
    assert single.returncode == 4
    assert list(out.iterdir()) == []


# --- lockfiles ---------------------------------------------------------------


def test_each_manifest_yields_a_lockfile(published):
    """Every satisfiable project in the manifest directory gets its lock."""
    for project in EXPECTED:
        assert lock_at(published, project).is_file(), project
    assert not lock_at(published, DEAD_END).exists()


def test_selected_versions_are_the_expected_ones(published):
    """resolution-algorithm.md fixes one version per package per project."""
    for project, want in EXPECTED.items():
        doc = load(lock_at(published, project))
        assert selection_of(doc) == want["packages"], project


def test_counters_show_assignments_and_retreats(published):
    """The stats block has to reflect the search that actually ran."""
    for project, want in EXPECTED.items():
        doc = load(lock_at(published, project))
        assert doc["stats"] == want["stats"], project
        assert doc["allow_yanked"] == want["allow_yanked"], project


def test_waivers_are_the_expected_ones(published):
    """Only a pin produces a waiver, and it names the range it rode over."""
    for project, want in EXPECTED.items():
        doc = load(lock_at(published, project))
        assert doc["waived"] == want["waived"], project


def test_fingerprint_covers_the_payload_not_the_artifact(published):
    """digest-spec.md hashes tab-separated payload lines, never the JSON."""
    for project in EXPECTED:
        doc = load(lock_at(published, project))
        assert doc["digest"] == reference_fingerprint(reference_lock_payload(doc)), project
        assert HEX64_RE.match(doc["digest"])
        assert doc["digest"] not in doc["project"]


def test_lockfile_bytes_follow_the_house_style(published):
    """Two-space indent, key order from lock-schema.json, no escaped angles."""
    raw = lock_at(published, "foundry").read_text(encoding="utf-8")
    assert raw.endswith("}\n") and not raw.endswith("}\n\n")
    assert '\n  "project": "foundry",' in raw
    assert "\\u003c" not in raw and "\\u003e" not in raw
    assert '">=2.0.0 <3.0.0"' in raw
    keys = [m.group(1) for m in re.finditer(r'^  "([a-z_]+)"', raw, re.M)]
    assert keys == ["protocol", "project", "allow_yanked", "packages", "waived", "stats", "digest"]


def test_foundry_attributes_every_requirer(published):
    """required_by carries the labels of the constraints that pulled a package."""
    doc = load(lock_at(published, "foundry"))
    by_name = {entry["name"]: entry for entry in doc["packages"]}
    assert by_name["basalt"]["required_by"] == ["chert@1.5.0", "gabbro@4.2.0"]
    assert by_name["schist"]["required_by"] == ["root"]
    assert by_name["quartz"]["required_by"] == ["dolomite@3.1.0", "marl@2.1.0"]
    assert [entry["name"] for entry in doc["packages"]] == sorted(by_name)


def test_kilnworks_turns_on_the_feature_edges(published):
    """A +feature group adds the edges that feature declares, and only those."""
    doc = load(lock_at(published, "kilnworks"))
    by_name = {entry["name"]: entry for entry in doc["packages"]}
    assert by_name["chert"]["features"] == ["trace"]
    assert by_name["quartz"]["features"] == ["simd"]
    assert by_name["dolomite"]["features"] == []
    assert {"name": "tuff", "range": "^0.4.0"} in by_name["chert"]["requires"]
    assert by_name["tuff"]["required_by"] == ["chert@1.5.0", "quartz@2.2.0"]


def test_brackenfield_resolves_the_edges_of_a_pinned_release(published):
    """A pin does not exempt its own release from contributing edges: dolomite
    is overridden to 2.8.0, but 2.8.0's own requirement on chert still has to be
    resolved, and that requirement's own basalt constraint still has to coexist
    with gabbro's — which is exactly what forces the one recorded retreat."""
    doc = load(lock_at(published, "brackenfield"))
    by_name = {entry["name"]: entry for entry in doc["packages"]}
    assert by_name["dolomite"]["required_by"] == ["schist@5.0.1"]
    assert {"name": "chert", "range": "~1.3.0"} in by_name["dolomite"]["requires"]
    assert by_name["chert"]["required_by"] == ["dolomite@2.8.0"]
    assert by_name["basalt"]["required_by"] == ["chert@1.3.0", "gabbro@4.1.1"]
    assert doc["waived"] == ["schist@5.0.1 requires dolomite ^3.0.0"]
    assert doc["stats"]["backtracks"] == 1
    walk = load(walk_at(published, "brackenfield"))
    gabbro_step = next(s for s in walk["steps"] if s["package"] == "gabbro")
    assert gabbro_step["candidates"] == ["4.2.0", "4.1.1"]
    assert gabbro_step["version"] == "4.1.1"


def test_driftworks_accepts_the_withdrawn_release(published):
    """allow-yanked true lets a withdrawn release stand when nothing else fits."""
    doc = load(lock_at(published, "driftworks"))
    entry = doc["packages"][0]
    assert (entry["name"], entry["version"]) == ("gneiss", "1.2.0")
    assert entry["yanked"] is True
    assert doc["allow_yanked"] is True


def test_crucible_picks_a_release_candidate_only_where_asked(published):
    """constraint-grammar.md hides prereleases from ranges that do not name one."""
    crucible = selection_of(load(lock_at(published, "crucible")))
    foundry = selection_of(load(lock_at(published, "foundry")))
    assert (crucible["flint"], crucible["gneiss"]) == ("1.0.0-rc.2", "1.1.0")
    assert (foundry["flint"], foundry["gneiss"]) == ("0.9.3", "1.1.0")


def test_slagworks_retreats_onto_the_older_gabbro(published):
    """The newest gabbro cannot stand next to the pinned marl line."""
    doc = load(lock_at(published, "slagworks"))
    assert doc["stats"]["backtracks"] == 2
    assert selection_of(doc) == EXPECTED["slagworks"]["packages"]


# --- the staging walk --------------------------------------------------------


def test_search_walk_lands_in_the_staging_snapshot(published):
    """The trail belongs under the staging directory, one file per project."""
    for project in WALKS:
        assert walk_at(published, project).is_file(), project


def test_walk_preserves_the_pick_order_and_candidates(published):
    """Steps are numbered in pick order and quote the list being iterated."""
    for project, want in WALKS.items():
        doc = load(walk_at(published, project))
        assert walk_of(doc) == want, project
        assert [s["step"] for s in doc["steps"]] == list(range(1, len(want) + 1))


def test_walk_fingerprint_covers_its_own_steps(published):
    """Recomputing the trail payload has to reproduce the published value."""
    for project in WALKS:
        doc = load(walk_at(published, project))
        assert doc["digest"] == reference_fingerprint(reference_walk_payload(doc)), project
        assert HEX64_RE.match(doc["digest"])


def test_walk_and_lockfile_tell_the_same_story(published):
    """Trail assignments and lock entries cannot disagree."""
    for project in WALKS:
        lock = load(lock_at(published, project))
        walk = load(walk_at(published, project))
        assert {s["package"]: s["version"] for s in walk["steps"]} == selection_of(lock)
        assert len(walk["steps"]) == lock["stats"]["assignments"]


# --- the project with no solution -------------------------------------------


def test_emberyard_names_the_package_it_deadlocked_on(published):
    """An exhausted search publishes the newest conflict it recorded."""
    doc = load(deadlock_at(published, DEAD_END))
    assert doc["package"] == EMBERYARD_DEADLOCK["package"]
    assert doc["constraints"] == EMBERYARD_DEADLOCK["constraints"]
    assert doc["backtracks"] == EMBERYARD_DEADLOCK["backtracks"]
    assert doc["digest"] == reference_fingerprint(reference_deadlock_payload(doc))


def test_emberyard_clears_the_artifacts_it_must_not_leave(published):
    """A project without a solution keeps no lock and no trail."""
    assert not lock_at(published, DEAD_END).exists()
    assert not walk_at(published, DEAD_END).exists()


def test_one_project_run_signals_a_dead_end(tmp_path):
    """A named project exits 3 when nothing satisfies it, 0 when something does."""
    fine = run_slate("resolve", "foundry", "--out", str(tmp_path))
    assert fine.returncode == 0, fine.stderr
    stuck = run_slate("resolve", DEAD_END, "--out", str(tmp_path))
    assert stuck.returncode == 3, stuck.stdout + stuck.stderr
    assert deadlock_at(tmp_path, DEAD_END).is_file()


# --- the ladder --------------------------------------------------------------


def test_ladder_covers_the_whole_manifest_directory(published):
    """The index rows every project with its status, satisfiable or not."""
    doc = load(ladder_at(published))
    assert [e["project"] for e in doc["projects"]] == sorted(list(EXPECTED) + [DEAD_END])
    by_project = {e["project"]: e for e in doc["projects"]}
    assert by_project[DEAD_END]["status"] == "unsatisfiable"
    assert by_project[DEAD_END]["packages"] == 0
    assert by_project["foundry"]["status"] == "locked"
    assert by_project["foundry"]["packages"] == 9
    for project, want in EXPECTED.items():
        assert by_project[project]["backtracks"] == want["stats"]["backtracks"], project


def test_ladder_echoes_each_project_fingerprint(published):
    """Every row carries that project's own digest, and the ladder its own."""
    doc = load(ladder_at(published))
    by_project = {e["project"]: e for e in doc["projects"]}
    for project in EXPECTED:
        assert by_project[project]["digest"] == load(lock_at(published, project))["digest"], project
    assert by_project[DEAD_END]["digest"] == load(deadlock_at(published, DEAD_END))["digest"]
    assert doc["digest"] == reference_fingerprint(reference_ladder_payload(doc))


def test_batch_run_returns_zero_even_with_a_dead_end(tmp_path):
    """A batch run reports per project in the ladder rather than failing."""
    proc = run_slate("resolve", "--all", "--out", str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert ladder_at(tmp_path).is_file()


# --- repeatability -----------------------------------------------------------


def test_a_second_pass_reproduces_the_first(tmp_path):
    """Two runs over unchanged inputs have to persist identical bytes."""
    first = tmp_path / "first"
    second = tmp_path / "second"
    resolve_batch(first)
    resolve_batch(second)
    for path in sorted(first.rglob("*.json")):
        twin = second / path.relative_to(first)
        assert twin.read_bytes() == path.read_bytes(), path.name


def test_default_output_directory_was_left_populated(published):
    """The instruction ends with a batch run into the default output directory."""
    for project in EXPECTED:
        assert load(lock_at(APP_OUT, project))["digest"] == load(lock_at(published, project))["digest"]
    assert load(ladder_at(APP_OUT))["digest"] == load(ladder_at(published))["digest"]
    assert load(deadlock_at(APP_OUT, DEAD_END))["digest"] == load(deadlock_at(published, DEAD_END))["digest"]


# --- the holdout library -----------------------------------------------------


def test_holdout_projects_resolve_as_predicted(holdout):
    """Packages the image never carried must resolve from the contracts alone."""
    fixtures = Path(os.environ["TB3_SLATE_FIXTURES"])
    assert (fixtures / "registry").is_dir()
    for project, want in HOLDOUT.items():
        doc = load(lock_at(holdout, project))
        assert selection_of(doc) == want["packages"], project
        assert doc["stats"] == want["stats"], project


def test_holdout_falls_back_to_the_older_line(holdout):
    """The newest candidate forces a dependency the root range refuses."""
    fixtures = Path(os.environ["TB3_SLATE_FIXTURES"])
    assert (fixtures / "manifests").is_dir()
    retreats = {name: want for name, want in HOLDOUT.items() if "steps" in want}
    assert retreats, "no holdout project exercises a retreat"
    for project, want in retreats.items():
        walk = load(walk_at(holdout, project))
        assert walk_of(walk) == want["steps"], project
        assert load(lock_at(holdout, project))["stats"]["backtracks"] == 2


def test_holdout_pin_waives_its_range(holdout):
    """An override in a project nobody has seen still records its waiver."""
    fixtures = Path(os.environ["TB3_SLATE_FIXTURES"])
    assert (fixtures / "manifests").is_dir()
    pinned = {name: want for name, want in HOLDOUT.items() if "waived" in want}
    assert pinned, "no holdout project exercises a pin"
    for project, want in pinned.items():
        doc = load(lock_at(holdout, project))
        assert doc["waived"] == want["waived"], project
        assert selection_of(doc) == want["packages"], project
    for project, want in HOLDOUT.items():
        if "waived" not in want:
            assert load(lock_at(holdout, project))["waived"] == [], project


def test_holdout_dead_end_has_no_solution(holdout):
    """Two lines that cannot meet produce a conflict artifact, not a lock."""
    fixtures = Path(os.environ["TB3_SLATE_FIXTURES"])
    assert (fixtures / "manifests").is_dir()
    stuck = HOLDOUT_DEADLOCK["project"]
    doc = load(deadlock_at(holdout, stuck))
    assert doc["package"] == HOLDOUT_DEADLOCK["package"]
    assert doc["constraints"] == HOLDOUT_DEADLOCK["constraints"]
    assert doc["backtracks"] == HOLDOUT_DEADLOCK["backtracks"]
    assert doc["digest"] == reference_fingerprint(reference_deadlock_payload(doc))
    assert not lock_at(holdout, stuck).exists()


def test_holdout_ladder_covers_the_unseen_projects(holdout):
    """The ladder over unseen projects carries each row's own digest."""
    fixtures = Path(os.environ["TB3_SLATE_FIXTURES"])
    assert (fixtures / "registry").is_dir()
    doc = load(ladder_at(holdout))
    assert [e["project"] for e in doc["projects"]] == sorted(
        list(HOLDOUT) + [HOLDOUT_DEADLOCK["project"]]
    )
    by_project = {e["project"]: e for e in doc["projects"]}
    for project in HOLDOUT:
        assert by_project[project]["digest"] == load(lock_at(holdout, project))["digest"], project
    assert doc["digest"] == reference_fingerprint(reference_ladder_payload(doc))


def test_holdout_artifacts_agree_among_themselves(holdout):
    """Lock and trail of an unseen project have to describe one search."""
    fixtures = Path(os.environ["TB3_SLATE_FIXTURES"])
    assert (fixtures / "registry").is_dir()
    for project in HOLDOUT:
        lock = load(lock_at(holdout, project))
        walk = load(walk_at(holdout, project))
        assert lock["digest"] == reference_fingerprint(reference_lock_payload(lock)), project
        assert walk["digest"] == reference_fingerprint(reference_walk_payload(walk)), project
        assert {s["package"]: s["version"] for s in walk["steps"]} == selection_of(lock), project


# --- edited inputs -----------------------------------------------------------


def test_withdrawing_basalt_reshapes_the_closure(tmp_path):
    """Marking 2.3.0 yanked forces an older gabbro and one retreat."""
    registry, manifests = copy_inputs(tmp_path)
    basalt = registry / "basalt.json"
    doc = json.loads(basalt.read_text(encoding="utf-8"))
    for release in doc["releases"]:
        if release["version"] == "2.3.0":
            release["yanked"] = True
    basalt.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    out = tmp_path / "out"
    proc = run_slate(
        "resolve", "foundry", "--registry", str(registry),
        "--manifests", str(manifests), "--out", str(out),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lock = load(lock_at(out, "foundry"))
    got = selection_of(lock)
    assert (got["basalt"], got["gabbro"]) == ("2.2.4", "4.1.1")
    assert lock["stats"]["backtracks"] == 1


def test_an_absent_package_file_is_bad_input(tmp_path):
    """A constraint naming an unpublished package exits 4."""
    registry, manifests = copy_inputs(tmp_path)
    (registry / "tuff.json").unlink()
    proc = run_slate(
        "resolve", "kilnworks", "--registry", str(registry),
        "--manifests", str(manifests), "--out", str(tmp_path / "out"),
    )
    assert proc.returncode == 4, proc.stdout + proc.stderr


def test_a_stray_manifest_directive_is_bad_input(tmp_path):
    """registry-format.md allows four directives and nothing else."""
    registry, manifests = copy_inputs(tmp_path)
    project = "brokenyard"
    (manifests / (project + ".slate")).write_text(
        "project brokenyard\nrequire chert ^1.5.0\nprefer chert 1.4.2\n", encoding="utf-8"
    )
    proc = run_slate(
        "resolve", project, "--registry", str(registry),
        "--manifests", str(manifests), "--out", str(tmp_path / "out"),
    )
    assert proc.returncode == 4, proc.stdout + proc.stderr


def test_a_pin_on_an_unpublished_version_is_bad_input(tmp_path):
    """An override has to name a version the registry actually publishes."""
    registry, manifests = copy_inputs(tmp_path)
    project = "ghostyard"
    (manifests / (project + ".slate")).write_text(
        "project ghostyard\nrequire gabbro ^4.2.0\noverride basalt 9.9.9\n", encoding="utf-8"
    )
    proc = run_slate(
        "resolve", project, "--registry", str(registry),
        "--manifests", str(manifests), "--out", str(tmp_path / "out"),
    )
    assert proc.returncode == 4, proc.stdout + proc.stderr


def test_widening_the_marl_range_changes_the_selection(tmp_path):
    """Relaxing the root range lets the newest gabbro stand with no retreat."""
    registry, manifests = copy_inputs(tmp_path)
    (manifests / ("slagworks" + ".slate")).write_text(
        "project slagworks\nrequire gabbro ^4.0.0\nrequire marl ^2.0.0\n", encoding="utf-8"
    )
    out = tmp_path / "out"
    proc = run_slate(
        "resolve", "slagworks", "--registry", str(registry),
        "--manifests", str(manifests), "--out", str(out),
    )
    assert proc.returncode == 0, proc.stderr
    lock = load(lock_at(out, "slagworks"))
    widened = selection_of(lock)
    assert (widened["gabbro"], widened["marl"]) == ("4.2.0", "2.1.0")
    assert lock["stats"]["backtracks"] == 0
