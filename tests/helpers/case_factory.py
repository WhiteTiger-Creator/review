"""Seeded hidden dungeon roots with parquet, contracts, and content."""

from __future__ import annotations

import json
import random
import shutil
import textwrap
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import yaml

from helpers.expectation_model import (
    dataset_digest,
    question_fingerprint,
)

SEED_YAML = 173
SEED_SCHEMA = 811
SEED_UNICODE = 20260711

PUBLIC_CONTRACTS = Path("/data/contracts")
PUBLIC_DATASET = Path("/data/trivia_qa_sample.parquet")


def _artifact(*parts: str) -> str:
    """Root-relative POSIX artifact path built from short path segments."""
    return Path(*parts).as_posix()


@dataclass
class DungeonCase:
    root: Path
    config: Path
    dataset: Path
    contracts: Path
    answers: Path | None
    state: Path
    output: Path
    description: str
    expected_issues: list[tuple[str, str, str]] = field(default_factory=list)
    expect_audit_success: bool = False
    expect_playthrough_success: bool = False
    expected_route: list[str] | None = None
    expected_score: int | None = None
    dataset_a: Path | None = None
    dataset_b: Path | None = None
    notes: dict[str, Any] = field(default_factory=dict)


def _rng(seed: int) -> random.Random:
    return random.Random(seed)


def _write_yaml(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _write_toml(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).strip() + "\n", encoding="utf-8")


def _copy_contracts(dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(PUBLIC_CONTRACTS, dest)
    for path in dest.rglob("*"):
        if path.is_file():
            path.chmod(0o644)


def _write_parquet(path: Path, rows: list[dict[str, Any]], *, physical_order: list[int] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = rows if physical_order is None else [rows[i] for i in physical_order]
    json_path = path.with_suffix(".json")
    json_path.write_text(json.dumps(ordered), encoding="utf-8")
    conn = duckdb.connect()
    try:
        conn.execute(
            f"""
            COPY (
              SELECT * FROM read_json_auto('{json_path}')
            ) TO '{path}' (FORMAT PARQUET)
            """
        )
    finally:
        conn.close()
        json_path.unlink(missing_ok=True)


def _base_rows(seed: int, count: int = 6) -> list[dict[str, Any]]:
    rng = _rng(seed)
    rows: list[dict[str, Any]] = []
    for i in range(count):
        qid = f"gen_{seed}_{i:02d}"
        question = f"Generated question {seed}-{i}?"
        rows.append(
            {
                "question_id": qid,
                "question": question,
                "answer_value": f"ans{i}",
                "answer_aliases": [f"alias{i}"],
                "category": rng.choice(["history", "science", "arts"]),
                "difficulty": (i % 4) + 1,
                "source_split": "train",
            }
        )
    rows.sort(key=lambda r: r["question_id"])
    return rows


def _minimal_valid_layout(
    root: Path,
    *,
    seed: int,
    room_count: int = 3,
    start_room: str = "entry",
    exit_room: str = "exit",
    use_aliases: bool = False,
) -> tuple[Path, Path, list[dict[str, Any]]]:
    rows = _base_rows(seed, max(room_count, 3))
    dataset = root / "data" / "dataset.parquet"
    _write_parquet(dataset, rows)

    content = root / "bundle"
    rooms = content / "chambers"
    encounters = content / "nodes"
    scoring = content / "weights"
    config_dir = root / "config"

    if use_aliases:
        rooms.mkdir(parents=True, exist_ok=True)
        (rooms / "aliases.yaml").write_text(
            "start-alias: entry\nmid-alias: middle\n",
            encoding="utf-8",
        )

    room_names = ["entry", "middle", "exit"][:room_count]
    if len(room_names) < room_count:
        room_names = [f"room{i}" for i in range(room_count)]
        room_names[-1] = exit_room

    first_room_id = room_names[0]
    enc_ids: list[str] = []
    for idx, room_id in enumerate(room_names):
        enc_id = f"enc-{room_id}"
        enc_ids.append(enc_id)
        exits: dict[str, str] = {}
        if idx + 1 < len(room_names):
            target = room_names[idx + 1]
            if use_aliases and idx == 0:
                exits["default"] = "mid-alias"
            else:
                exits["default"] = target
        _write_yaml(
            rooms / f"{idx:02d}-{room_id}.yaml",
            {
                "version": "1",
                "id": room_id,
                "title": room_id.title(),
                "encounters": [enc_id] if room_id != exit_room else [],
                "exits": exits,
            },
        )
        if room_id != exit_room:
            row = rows[idx % len(rows)]
            _write_yaml(
                encounters / f"{enc_id}.yaml",
                {
                    "version": "1",
                    "id": enc_id,
                    "room": room_id,
                    "title": enc_id,
                    "trivia": {"question_id": row["question_id"]},
                },
            )

    _write_yaml(scoring / "base.yaml", {"version": "1", "base": {"correct_points": 10, "wrong_points": 0}})
    _write_yaml(
        scoring / "streaks.yaml",
        {"version": "1", "streaks": {"bonuses": [{"threshold": 2, "bonus": 5}]}},
    )
    _write_yaml(
        scoring / "difficulty.yaml",
        {
            "version": "1",
            "difficulty": {"tiers": [{"min": 2, "multiplier": 1.2}, {"min": 3, "multiplier": 1.5}]},
        },
    )

    config = config_dir / "dungeon.toml"
    start = "start-alias" if use_aliases else first_room_id
    _write_toml(
        config,
        f"""
        version = "1"

        [dungeon]
        root = "."
        content_dir = "bundle"
        start_room = "{start}"
        exit_room = "{exit_room}"
        state = ".state/audit-state.json"
        output = "output"
        dataset = "data/dataset.parquet"
        contracts = "contracts"
        """,
    )
    return config, dataset, rows


def _read_toml_string(config: Path, key: str, default: str) -> str:
    for line in config.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{key} ="):
            return stripped.split("=", 1)[1].strip().strip('"')
    return default


def _load_scoring_model(scoring_dir: Path) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for path in sorted(scoring_dir.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        for key, value in doc.items():
            if key == "version":
                continue
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
    return merged


def build_valid_dungeon(tmp_path: Path, seed: int) -> DungeonCase:
    root = tmp_path / f"valid-{seed}"
    root.mkdir(parents=True, exist_ok=True)
    contracts = root / "contracts"
    _copy_contracts(contracts)
    config, dataset, rows = _minimal_valid_layout(root, seed=seed, room_count=3 + (seed % 3))
    answers = root / "config" / "answers.toml"
    answer_lines = ['version = "1"', "", "[answers]"]
    for enc_path in sorted((root / "bundle" / "nodes").glob("*.yaml")):
        doc = yaml.safe_load(enc_path.read_text(encoding="utf-8"))
        qid = doc["trivia"]["question_id"]
        answer = next(r["answer_value"] for r in rows if r["question_id"] == qid)
        answer_lines.append(f'{doc["id"]} = "{answer}"')
    _write_toml(answers, "\n".join(answer_lines))

    from helpers.expectation_model import GraphModel, simulate_playthrough

    start_room = _read_toml_string(config, "start_room", "entry")
    scoring_model = _load_scoring_model(root / "bundle" / "weights")
    room_docs = {
        path: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in (root / "bundle" / "chambers").glob("*.yaml")
        if path.name != "aliases.yaml"
    }
    encounter_docs = {
        path: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in (root / "bundle" / "nodes").glob("*.yaml")
    }
    model = GraphModel(
        rooms={doc["id"]: doc for doc in room_docs.values()},
        encounters={
            doc["id"]: {
                **doc,
                "resolved_question": next(
                    r for r in rows if r["question_id"] == doc["trivia"]["question_id"]
                ),
            }
            for doc in encounter_docs.values()
        },
        aliases=yaml.safe_load((root / "bundle" / "chambers" / "aliases.yaml").read_text(encoding="utf-8"))
        if (root / "bundle" / "chambers" / "aliases.yaml").exists()
        else {},
        scoring=scoring_model,
        start_room=start_room,
        exit_room=_read_toml_string(config, "exit_room", "exit"),
    )
    sim = simulate_playthrough(model, {line.split("=")[0].strip(): line.split("=")[1].strip().strip('"') for line in answer_lines[3:]})

    return DungeonCase(
        root=root,
        config=config,
        dataset=dataset,
        contracts=contracts,
        answers=answers,
        state=root / ".state" / "state.json",
        output=root / "output",
        description=f"valid generated dungeon seed={seed}",
        expect_audit_success=True,
        expect_playthrough_success=True,
        expected_route=sim["visited_rooms"],
        expected_score=sim["total_score"],
        notes={"room_count": len(list((root / "bundle" / "chambers").glob('*.yaml')))},
    )


def build_yaml_scalar_case(tmp_path: Path, seed: int = SEED_YAML) -> DungeonCase:
    root = tmp_path / f"yaml12-{seed}"
    root.mkdir(parents=True, exist_ok=True)
    contracts = root / "contracts"
    _copy_contracts(contracts)
    config, dataset, rows = _minimal_valid_layout(root, seed=seed, room_count=3)
    rooms = root / "bundle" / "chambers"
    _write_yaml(
        rooms / "keywords.yaml",
        {
            "version": "1",
            "id": "on",
            "title": "Keyword Room",
            "encounters": [],
            "exits": {"default": "exit"},
        },
    )
    _write_yaml(
        rooms / "off-room.yaml",
        {
            "version": "1",
            "id": "off",
            "title": "Off Room",
            "encounters": [],
            "exits": {"default": "exit"},
        },
    )
    return DungeonCase(
        root=root,
        config=config,
        dataset=dataset,
        contracts=contracts,
        answers=None,
        state=root / ".state" / "state.json",
        output=root / "output",
        description="yaml 1.2 scalar semantics",
        expect_audit_success=True,
        notes={"keyword_room_ids": ["on", "off"]},
    )


def build_aggregated_errors_case(tmp_path: Path, seed: int = SEED_YAML) -> DungeonCase:
    root = tmp_path / f"aggregate-{seed}"
    root.mkdir(parents=True, exist_ok=True)
    contracts = root / "contracts"
    _copy_contracts(contracts)
    config, dataset, _rows = _minimal_valid_layout(root, seed=seed, room_count=3)
    rooms = root / "bundle" / "chambers"
    _write_yaml(
        rooms / "01-broken.yaml",
        {
            "version": "1",
            "id": "broken",
            # title intentionally missing
            "encounters": [],
            "exits": {"default": "missing-room"},
        },
    )
    _write_yaml(
        root / "bundle" / "weights" / "bad-streaks.yaml",
        {
            "version": "1",
            "streaks": {"bonuses": [{"threshold": "2", "bonus": 5}]},
        },
    )
    expected = [
        (_artifact("bundle", "chambers", "01-broken.yaml"), "/title", "schema.required"),
        (_artifact("bundle", "weights", "bad-streaks.yaml"), "/streaks/bonuses/0/threshold", "schema.type"),
        (_artifact("bundle", "chambers", "01-broken.yaml"), "/exits/default", "graph.unknown-room"),
    ]
    return DungeonCase(
        root=root,
        config=config,
        dataset=dataset,
        contracts=contracts,
        answers=None,
        state=root / ".state" / "state.json",
        output=root / "output",
        description="aggregated schema and graph findings",
        expected_issues=expected,
    )


def build_schema_variant_case(tmp_path: Path, seed: int = SEED_SCHEMA) -> DungeonCase:
    root = tmp_path / f"schema-variant-{seed}"
    root.mkdir(parents=True, exist_ok=True)
    contracts = root / "contracts"
    _copy_contracts(contracts)
    schema_path = contracts / "encounter.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["properties"]["subtitle"] = {"type": "string"}
    schema["required"].append("subtitle")
    schema_path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    config, dataset, rows = _minimal_valid_layout(root, seed=seed, room_count=3)
    enc = root / "bundle" / "nodes"
    rooms = root / "bundle" / "chambers"
    for path in enc.glob("*.yaml"):
        path.unlink()
    for path in rooms.glob("*.yaml"):
        if path.name == "aliases.yaml":
            continue
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        doc["encounters"] = []
        _write_yaml(path, doc)
    _write_yaml(
        enc / "matching.yaml",
        {
            "version": "1",
            "id": "enc-match",
            "room": "entry",
            "title": "Match",
            "subtitle": "extra",
            "trivia": {"question_id": rows[0]["question_id"]},
        },
    )
    _write_yaml(
        enc / "nonmatching.yaml",
        {
            "version": "1",
            "id": "enc-miss",
            "room": "middle",
            "title": "Miss",
            "trivia": {"question_id": rows[1]["question_id"]},
        },
    )
    return DungeonCase(
        root=root,
        config=config,
        dataset=dataset,
        contracts=contracts,
        answers=None,
        state=root / ".state" / "state.json",
        output=root / "output",
        description="data-driven schema selection",
        expected_issues=[(_artifact("bundle", "nodes", "nonmatching.yaml"), "/subtitle", "schema.required")],
        notes={"passing_encounter": "enc-match"},
    )


def build_modern_id_case(tmp_path: Path, seed: int = SEED_SCHEMA) -> DungeonCase:
    root = tmp_path / f"modern-id-{seed}"
    root.mkdir(parents=True, exist_ok=True)
    contracts = root / "contracts"
    _copy_contracts(contracts)
    rows = [
        {
            "question_id": "uniq_1",
            "question": "Unique?",
            "answer_value": "u",
            "answer_aliases": [],
            "category": "science",
            "difficulty": 2,
            "source_split": "train",
        },
        {
            "question_id": "dup_x",
            "question": "Dup A?",
            "answer_value": "a",
            "answer_aliases": [],
            "category": "science",
            "difficulty": 2,
            "source_split": "train",
        },
        {
            "question_id": "dup_x",
            "question": "Dup B?",
            "answer_value": "b",
            "answer_aliases": [],
            "category": "science",
            "difficulty": 3,
            "source_split": "validation",
        },
    ]
    rows.sort(key=lambda r: r["question_id"])
    dataset = root / "data" / "dataset.parquet"
    config, _, _ = _minimal_valid_layout(root, seed=seed, room_count=3)
    _write_parquet(dataset, rows)
    enc = root / "bundle" / "nodes"
    rooms = root / "bundle" / "chambers"
    for path in enc.glob("*.yaml"):
        path.unlink()
    for path in rooms.glob("*.yaml"):
        if path.name == "aliases.yaml":
            continue
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        doc["encounters"] = []
        _write_yaml(path, doc)
    for label, qid in [("unique", "uniq_1"), ("missing", "missing_zzz"), ("duplicate", "dup_x")]:
        _write_yaml(
            enc / f"{label}.yaml",
            {
                "version": "1",
                "id": f"enc-{label}",
                "room": "entry",
                "title": label,
                "trivia": {"question_id": qid},
            },
        )
    expected = [
        (_artifact("bundle", "nodes", "missing.yaml"), "/trivia/question_id", "dataset.missing-id"),
        (_artifact("bundle", "nodes", "duplicate.yaml"), "/trivia/question_id", "dataset.ambiguous-id"),
    ]
    return DungeonCase(
        root=root,
        config=config,
        dataset=dataset,
        contracts=contracts,
        answers=None,
        state=root / ".state" / "state.json",
        output=root / "output",
        description="modern question_id uniqueness",
        expected_issues=expected,
        notes={"unique_id": "uniq_1"},
    )


def _legacy_single_case(
    tmp_path: Path,
    *,
    seed: int,
    label: str,
    rows: list[dict[str, Any]],
    physical_order: list[int],
    target: dict[str, Any],
) -> DungeonCase:
    root = tmp_path / f"legacy-{label}-{seed}"
    root.mkdir(parents=True, exist_ok=True)
    contracts = root / "contracts"
    _copy_contracts(contracts)
    dataset = root / "data" / "dataset.parquet"
    _write_parquet(dataset, rows, physical_order=physical_order)
    content = root / "bundle"
    rooms = content / "chambers"
    encounters = content / "nodes"
    scoring = content / "weights"
    for sub in (rooms, encounters, scoring):
        sub.mkdir(parents=True, exist_ok=True)
    _write_yaml(scoring / "base.yaml", {"version": "1", "base": {"correct_points": 10, "wrong_points": 0}})
    _write_yaml(
        rooms / "00-entry.yaml",
        {"version": "1", "id": "entry", "title": "Entry", "encounters": ["legacy-enc"], "exits": {"default": "exit"}},
    )
    _write_yaml(
        rooms / "01-exit.yaml",
        {"version": "1", "id": "exit", "title": "Exit", "encounters": [], "exits": {}},
    )
    _write_yaml(
        encounters / "legacy-enc.yaml",
        {
            "version": "1",
            "id": "legacy-enc",
            "room": "entry",
            "title": "Legacy",
            "trivia": {"row": target["canonical_row"], "question_sha256": target["question_sha256"]},
        },
    )
    config = root / "config" / "dungeon.toml"
    _write_toml(
        config,
        """
        version = "1"
        [dungeon]
        root = "."
        content_dir = "bundle"
        start_room = "entry"
        exit_room = "exit"
        state = ".state/state.json"
        output = "output"
        dataset = "data/dataset.parquet"
        contracts = "contracts"
        """,
    )
    return DungeonCase(
        root=root,
        config=config,
        dataset=dataset,
        contracts=contracts,
        answers=None,
        state=root / ".state" / "state.json",
        output=root / "output",
        description=f"legacy reorder {label}",
        expect_audit_success=True,
        notes={"question_id": target["question_id"], "dataset_digest": dataset_digest(dataset)},
    )


def build_legacy_reorder_case(tmp_path: Path, seed: int = SEED_YAML) -> tuple[DungeonCase, DungeonCase]:
    rows = _base_rows(seed, 5)
    canon = canonical_rows_from_rows(rows)
    target = canon[2]
    case_a = _legacy_single_case(
        tmp_path,
        seed=seed,
        label="order-a",
        rows=rows,
        physical_order=list(range(len(rows))),
        target=target,
    )
    case_b = _legacy_single_case(
        tmp_path,
        seed=seed,
        label="order-b",
        rows=rows,
        physical_order=list(reversed(range(len(rows)))),
        target=target,
    )
    return case_a, case_b


def canonical_rows_from_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda r: r["question_id"])
    out = []
    for index, row in enumerate(ordered, start=1):
        item = dict(row)
        item["canonical_row"] = index
        item["question_sha256"] = question_fingerprint(row["question"])
        out.append(item)
    return out


def build_stale_fingerprint_case(tmp_path: Path, seed: int = SEED_SCHEMA) -> DungeonCase:
    root = tmp_path / f"stale-fp-{seed}"
    root.mkdir(parents=True, exist_ok=True)
    contracts = root / "contracts"
    _copy_contracts(contracts)
    rows = _base_rows(seed, 4)
    dataset = root / "data" / "dataset.parquet"
    _write_parquet(dataset, rows)
    canon = canonical_rows_from_rows(rows)
    target = canon[1]
    config, _, _ = _minimal_valid_layout(root, seed=seed, room_count=3)
    _write_yaml(
        root / "bundle" / "nodes" / "stale.yaml",
        {
            "version": "1",
            "id": "stale-enc",
            "room": "entry",
            "title": "Stale",
            "trivia": {"row": target["canonical_row"], "question_sha256": "f" * 64},
        },
    )
    return DungeonCase(
        root=root,
        config=config,
        dataset=dataset,
        contracts=contracts,
        answers=None,
        state=root / ".state" / "state.json",
        output=root / "output",
        description="stale legacy fingerprint",
        expected_issues=[(_artifact("bundle", "nodes", "stale.yaml"), "/trivia/question_sha256", "dataset.fingerprint-mismatch")],
    )


def build_unicode_alias_case(tmp_path: Path, seed: int = SEED_UNICODE) -> DungeonCase:
    root = tmp_path / f"unicode-{seed}"
    root.mkdir(parents=True, exist_ok=True)
    contracts = root / "contracts"
    _copy_contracts(contracts)
    nfc = "İstanbul"
    nfd = unicodedata.normalize("NFD", nfc)
    rows = [
        {
            "question_id": "uni_capital",
            "question": f"What city? {nfc}",
            "answer_value": "istanbul",
            "answer_aliases": None,
            "category": "geography",
            "difficulty": 3,
            "source_split": "train",
        },
        {
            "question_id": "uni_empty",
            "question": "Empty aliases?",
            "answer_value": "empty",
            "answer_aliases": [],
            "category": "mixed",
            "difficulty": 2,
            "source_split": "train",
        },
    ]
    dataset = root / "data" / "dataset.parquet"
    config, _, _ = _minimal_valid_layout(root, seed=seed, room_count=3, use_aliases=True)
    _write_parquet(dataset, rows)
    enc = root / "bundle" / "nodes"
    rooms = root / "bundle" / "chambers"
    for path in enc.glob("*.yaml"):
        path.unlink()
    for path in rooms.glob("*.yaml"):
        if path.name == "aliases.yaml":
            continue
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        doc["encounters"] = []
        _write_yaml(path, doc)
    _write_yaml(
        enc / "enc-entry.yaml",
        {
            "version": "1",
            "id": "enc-entry",
            "room": "entry",
            "title": "Entry",
            "trivia": {"question_id": "uni_empty"},
        },
    )
    entry_room = rooms / "00-entry.yaml"
    entry_doc = yaml.safe_load(entry_room.read_text(encoding="utf-8"))
    entry_doc["encounters"] = ["enc-entry", "uni-enc"]
    _write_yaml(entry_room, entry_doc)
    _write_yaml(
        enc / "uni-enc.yaml",
        {
            "version": "1",
            "id": "uni-enc",
            "room": "entry",
            "title": "Unicode",
            "trivia": {"question_id": "uni_capital"},
        },
    )
    answers = root / "config" / "answers.toml"
    _write_toml(
        answers,
        """
        version = "1"
        [answers]
        enc-entry = "istanbul"
        uni-enc = "  İSTANBUL  "
        """,
    )
    return DungeonCase(
        root=root,
        config=config,
        dataset=dataset,
        contracts=contracts,
        answers=answers,
        state=root / ".state" / "state.json",
        output=root / "output",
        description="unicode and null alias normalization",
        expect_audit_success=True,
        expect_playthrough_success=True,
        notes={"nfc_question": nfc, "nfd_question": nfd},
    )


def build_alias_playthrough_case(tmp_path: Path, seed: int = SEED_UNICODE) -> DungeonCase:
    root = tmp_path / f"alias-play-{seed}"
    root.mkdir(parents=True, exist_ok=True)
    contracts = root / "contracts"
    _copy_contracts(contracts)
    rows = _base_rows(seed, 3)
    legacy = canonical_rows_from_rows(rows)[0]
    dataset = root / "data" / "dataset.parquet"
    _write_parquet(dataset, rows)
    config, _, _ = _minimal_valid_layout(root, seed=seed, room_count=3, use_aliases=True)
    _write_yaml(
        root / "bundle" / "nodes" / "legacy.yaml",
        {
            "version": "1",
            "id": "legacy",
            "room": "middle",
            "title": "Legacy locator",
            "trivia": {"row": legacy["canonical_row"], "question_sha256": legacy["question_sha256"]},
        },
    )
    answers = root / "config" / "verification-answers.toml"
    _write_toml(
        answers,
        f"""
        version = "1"
        [answers]
        enc-entry = "{rows[0]['answer_value']}"
        legacy = "{rows[0]['answer_value']}"
        enc-middle = "{rows[1]['answer_value']}"
        """,
    )
    return DungeonCase(
        root=root,
        config=config,
        dataset=dataset,
        contracts=contracts,
        answers=answers,
        state=root / ".state" / "state.json",
        output=root / "output",
        description="alias playthrough with legacy locator",
        expect_audit_success=True,
        expect_playthrough_success=True,
        expected_route=["entry", "middle", "exit"],
    )


def build_cycle_case(tmp_path: Path, seed: int = SEED_YAML) -> DungeonCase:
    root = tmp_path / f"cycle-{seed}"
    root.mkdir(parents=True, exist_ok=True)
    contracts = root / "contracts"
    _copy_contracts(contracts)
    config, dataset, _ = _minimal_valid_layout(root, seed=seed, room_count=1)
    rooms = root / "bundle" / "chambers"
    _write_yaml(rooms / "00-a.yaml", {"version": "1", "id": "a", "title": "A", "encounters": [], "exits": {"default": "b"}})
    _write_yaml(rooms / "01-b.yaml", {"version": "1", "id": "b", "title": "B", "encounters": [], "exits": {"default": "a"}})
    _write_toml(
        root / "config" / "dungeon.toml",
        """
        version = "1"
        [dungeon]
        root = "."
        content_dir = "bundle"
        start_room = "a"
        exit_room = "exit"
        state = ".state/state.json"
        output = "output"
        dataset = "data/dataset.parquet"
        contracts = "contracts"
        """,
    )
    return DungeonCase(
        root=root,
        config=root / "config" / "dungeon.toml",
        dataset=dataset,
        contracts=contracts,
        answers=None,
        state=root / ".state" / "state.json",
        output=root / "output",
        description="graph cycle without exit",
        expected_issues=[(_artifact("bundle", "chambers", "00-a.yaml"), "/exits", "graph.cycle")],
    )


def build_dead_end_case(tmp_path: Path, seed: int = SEED_SCHEMA) -> DungeonCase:
    root = tmp_path / f"dead-end-{seed}"
    root.mkdir(parents=True, exist_ok=True)
    contracts = root / "contracts"
    _copy_contracts(contracts)
    config, dataset, _ = _minimal_valid_layout(root, seed=seed, room_count=1)
    _write_yaml(
        root / "bundle" / "chambers" / "00-trap.yaml",
        {"version": "1", "id": "trap", "title": "Trap", "encounters": [], "exits": {}},
    )
    _write_toml(
        root / "config" / "dungeon.toml",
        """
        version = "1"
        [dungeon]
        root = "."
        content_dir = "bundle"
        start_room = "trap"
        exit_room = "exit"
        state = ".state/state.json"
        output = "output"
        dataset = "data/dataset.parquet"
        contracts = "contracts"
        """,
    )
    return DungeonCase(
        root=root,
        config=root / "config" / "dungeon.toml",
        dataset=dataset,
        contracts=contracts,
        answers=None,
        state=root / ".state" / "state.json",
        output=root / "output",
        description="dead-end room",
        expected_issues=[(_artifact("bundle", "chambers", "00-trap.yaml"), "/exits", "graph.dead-end")],
    )


def build_score_boundary_case(tmp_path: Path, seed: int = SEED_UNICODE) -> DungeonCase:
    root = tmp_path / f"score-boundary-{seed}"
    root.mkdir(parents=True, exist_ok=True)
    contracts = root / "contracts"
    _copy_contracts(contracts)
    rows = [
        {
            "question_id": "bound_1",
            "question": "Boundary?",
            "answer_value": "ok",
            "answer_aliases": [],
            "category": "science",
            "difficulty": 2,
            "source_split": "train",
        },
        {
            "question_id": "bound_2",
            "question": "Boundary 2?",
            "answer_value": "ok2",
            "answer_aliases": [],
            "category": "science",
            "difficulty": 2,
            "source_split": "train",
        },
    ]
    dataset = root / "data" / "dataset.parquet"
    config, _, _ = _minimal_valid_layout(root, seed=seed, room_count=3)
    _write_parquet(dataset, rows)
    enc = root / "bundle" / "nodes"
    rooms = root / "bundle" / "chambers"
    for path in enc.glob("*.yaml"):
        path.unlink()
    for path in rooms.glob("*.yaml"):
        if path.name == "aliases.yaml":
            continue
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        doc["encounters"] = []
        _write_yaml(path, doc)
    _write_yaml(
        root / "bundle" / "weights" / "streaks.yaml",
        {"version": "1", "streaks": {"bonuses": [{"threshold": 2, "bonus": 7}]}},
    )
    _write_yaml(
        enc / "enc-entry.yaml",
        {"version": "1", "id": "enc-entry", "room": "entry", "title": "E1", "trivia": {"question_id": "bound_1"}},
    )
    _write_yaml(
        enc / "enc-middle.yaml",
        {"version": "1", "id": "enc-middle", "room": "middle", "title": "E2", "trivia": {"question_id": "bound_2"}},
    )
    entry_doc = yaml.safe_load((rooms / "00-entry.yaml").read_text(encoding="utf-8"))
    entry_doc["encounters"] = ["enc-entry"]
    _write_yaml(rooms / "00-entry.yaml", entry_doc)
    middle_doc = yaml.safe_load((rooms / "01-middle.yaml").read_text(encoding="utf-8"))
    middle_doc["encounters"] = ["enc-middle"]
    _write_yaml(rooms / "01-middle.yaml", middle_doc)
    answers = root / "config" / "answers.toml"
    _write_toml(
        answers,
        """
        version = "1"
        [answers]
        enc-entry = "ok"
        enc-middle = "ok2"
        """,
    )
    scoring = {
        "base": {"correct_points": 10, "wrong_points": 0},
        "streaks": {"bonuses": [{"threshold": 2, "bonus": 7}]},
        "difficulty": {"tiers": [{"min": 2, "multiplier": 1.2}]},
    }
    from helpers.expectation_model import score_encounter

    expected_score = score_encounter(True, 2, 1, scoring) + score_encounter(True, 2, 2, scoring)
    return DungeonCase(
        root=root,
        config=config,
        dataset=dataset,
        contracts=contracts,
        answers=answers,
        state=root / ".state" / "state.json",
        output=root / "output",
        description="inclusive streak threshold boundary",
        expect_audit_success=True,
        expect_playthrough_success=True,
        expected_score=expected_score,
    )


def build_precedence_case(tmp_path: Path) -> DungeonCase:
    root = tmp_path / "precedence"
    root.mkdir(parents=True, exist_ok=True)
    contracts_a = root / "contracts_a"
    contracts_b = root / "contracts_b"
    _copy_contracts(contracts_a)
    _copy_contracts(contracts_b)
    rows_a = [{"question_id": "ds_a", "question": "A?", "answer_value": "a", "answer_aliases": [], "category": "x", "difficulty": 1, "source_split": "train"}]
    rows_b = [{"question_id": "ds_b", "question": "B?", "answer_value": "b", "answer_aliases": [], "category": "x", "difficulty": 1, "source_split": "train"}]
    dataset_a = root / "datasets" / "a.parquet"
    dataset_b = root / "datasets" / "b.parquet"
    _write_parquet(dataset_a, rows_a)
    _write_parquet(dataset_b, rows_b)
    nested = root / "nested" / "config"
    nested.mkdir(parents=True, exist_ok=True)
    content = root / "bundle"
    rooms = content / "chambers"
    encounters = content / "nodes"
    scoring = content / "weights"
    for sub in (rooms, encounters, scoring):
        sub.mkdir(parents=True, exist_ok=True)
    _write_yaml(scoring / "base.yaml", {"version": "1", "base": {"correct_points": 10, "wrong_points": 0}})
    _write_yaml(rooms / "00-entry.yaml", {"version": "1", "id": "entry", "title": "Entry", "encounters": ["probe"], "exits": {"default": "exit"}})
    _write_yaml(rooms / "01-exit.yaml", {"version": "1", "id": "exit", "title": "Exit", "encounters": [], "exits": {}})
    _write_yaml(
        encounters / "probe.yaml",
        {"version": "1", "id": "probe", "room": "entry", "title": "Probe", "trivia": {"question_id": "ds_a"}},
    )
    config = nested / "dungeon.toml"
    _write_toml(
        config,
        f"""
        version = "1"
        [dungeon]
        root = "{root.as_posix()}"
        content_dir = "bundle"
        start_room = "entry"
        exit_room = "exit"
        state = "../../.state/state.json"
        output = "../../output"
        dataset = "{dataset_a.as_posix()}"
        contracts = "{contracts_a.as_posix()}"
        """,
    )
    return DungeonCase(
        root=root,
        config=config,
        dataset=dataset_a,
        contracts=contracts_a,
        answers=None,
        state=root / ".state" / "state.json",
        output=root / "output",
        description="cli/env/toml precedence",
        expect_audit_success=True,
        dataset_a=dataset_a,
        dataset_b=dataset_b,
        notes={"contracts_b": str(contracts_b), "dataset_b": str(dataset_b)},
    )
