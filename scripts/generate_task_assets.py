#!/usr/bin/env python3
"""Generate contracts, parquet dataset, bundled content, and fixture hashes."""

from __future__ import annotations

import hashlib
import json
import shutil
import unicodedata
from pathlib import Path

import subprocess

TASK = Path(__file__).resolve().parents[1]
DUCKDB = Path("/tmp/duckdb-cli/duckdb")
ENV = TASK / "environment"
CONTRACTS = ENV / "contracts"
DATA = ENV / "data"
APP = ENV / "app"
TESTS = TASK / "tests"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def question_fingerprint(question: str) -> str:
    text = unicodedata.normalize("NFC", question).casefold()
    stripped = "".join(c if c.isalnum() or c.isspace() else "" for c in text)
    collapsed = " ".join(stripped.split())
    return hashlib.sha256(collapsed.encode("utf-8")).hexdigest()


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def generate_contracts() -> None:
    version = {"$defs": {"version": {"type": "string", "const": "1"}}}
    write_json(
        CONTRACTS / "aliases.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": {"type": "string"},
        },
    )
    write_json(
        CONTRACTS / "room.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "id", "title", "encounters", "exits"],
            "properties": {
                "version": {"$ref": "#/$defs/version"},
                "id": {"type": "string", "minLength": 1},
                "title": {"type": "string"},
                "encounters": {
                    "type": "array",
                    "items": {"type": "string"},
                    "uniqueItems": True,
                },
                "exits": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                },
            },
            **version,
        },
    )
    write_json(
        CONTRACTS / "encounter.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "id", "room", "title", "trivia"],
            "properties": {
                "version": {"$ref": "#/$defs/version"},
                "id": {"type": "string"},
                "room": {"type": "string"},
                "title": {"type": "string"},
                "trivia": {
                    "oneOf": [
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["question_id"],
                            "properties": {"question_id": {"type": "string"}},
                        },
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["row", "question_sha256"],
                            "properties": {
                                "row": {"type": "integer", "minimum": 1},
                                "question_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                            },
                        },
                    ]
                },
            },
            **version,
        },
    )
    write_json(
        CONTRACTS / "scoring.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": False,
            "required": ["version"],
            "properties": {
                "version": {"$ref": "#/$defs/version"},
                "base": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "correct_points": {"type": "integer"},
                        "wrong_points": {"type": "integer"},
                    },
                },
                "difficulty": {
                    "type": "object",
                    "properties": {
                        "tiers": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["min", "multiplier"],
                                "properties": {
                                    "min": {"type": "integer"},
                                    "multiplier": {"type": "number"},
                                },
                            },
                        }
                    },
                },
                "streaks": {
                    "type": "object",
                    "properties": {
                        "bonuses": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["threshold", "bonus"],
                                "properties": {
                                    "threshold": {"type": "integer"},
                                    "bonus": {"type": "integer"},
                                },
                            },
                        }
                    },
                },
            },
            **version,
        },
    )
    write_json(
        CONTRACTS / "dungeon-config.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "dungeon"],
            "properties": {
                "version": {"$ref": "#/$defs/version"},
                "dungeon": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "root": {"type": "string"},
                        "dataset": {"type": "string"},
                        "contracts": {"type": "string"},
                        "output": {"type": "string"},
                        "state": {"type": "string"},
                        "start_room": {"type": "string"},
                        "exit_room": {"type": "string"},
                        "content_dir": {"type": "string"},
                    },
                },
            },
            **version,
        },
    )
    write_json(
        CONTRACTS / "answers.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "answers"],
            "properties": {
                "version": {"$ref": "#/$defs/version"},
                "answers": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                },
            },
            **version,
        },
    )
    write_json(
        CONTRACTS / "audit-report.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": False,
            "required": [
                "input_digest",
                "registry_digest",
                "issue_count",
                "success",
                "issues",
                "artifacts",
            ],
            "properties": {
                "input_digest": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                "registry_digest": {"type": "string"},
                "issue_count": {"type": "integer", "minimum": 0},
                "success": {"type": "boolean"},
                "issues": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["artifact", "pointer", "code", "message"],
                        "properties": {
                            "artifact": {"type": "string"},
                            "pointer": {"type": "string"},
                            "code": {"type": "string"},
                            "message": {"type": "string"},
                        },
                    },
                },
                "artifacts": {"type": "array", "items": {"type": "string"}},
            },
        },
    )
    write_json(
        CONTRACTS / "playthrough.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": False,
            "required": [
                "reached_exit",
                "total_score",
                "visited_rooms",
                "encounters",
                "registry_digest",
            ],
            "properties": {
                "reached_exit": {"type": "boolean"},
                "total_score": {"type": "integer"},
                "visited_rooms": {"type": "array", "items": {"type": "string"}},
                "encounters": {"type": "array", "items": {"type": "string"}},
                "registry_digest": {"type": "string"},
            },
        },
    )


def build_rows() -> list[dict]:
    rows = []
    categories = ["history", "science", "literature", "mixed", "geography", "arts"]
    for i in range(1, 51):
        qid = f"tc_{i:04d}"
        question = f"Bundled question number {i}?"
        answer = f"answer{i}"
        aliases = [f"alt{i}"] if i % 5 else []
        if i == 7:
            question = "What is the capital of Türkiye?"
            answer = "Ankara"
            aliases = ["ankara"]
        if i == 12:
            question = unicodedata.normalize("NFD", "Café résumé")
            answer = "resume"
            aliases = []
        if i == 18:
            aliases = None
        if i == 23:
            aliases = []
        rows.append(
            {
                "question_id": qid,
                "question": question,
                "answer_value": answer,
                "answer_aliases": aliases,
                "category": categories[i % len(categories)],
                "difficulty": (i % 5) + 1,
                "source_split": "train",
            }
        )
    rows.append(
        {
            "question_id": "tc_dup_001",
            "question": "Duplicate alpha?",
            "answer_value": "alpha",
            "answer_aliases": [],
            "category": "science",
            "difficulty": 2,
            "source_split": "train",
        }
    )
    rows.append(
        {
            "question_id": "tc_dup_001",
            "question": "Duplicate beta?",
            "answer_value": "beta",
            "answer_aliases": [],
            "category": "science",
            "difficulty": 3,
            "source_split": "validation",
        }
    )
    rows.sort(key=lambda r: r["question_id"])
    return rows


def generate_parquet() -> dict[str, dict]:
    rows = build_rows()
    canonical = {r["question_id"]: r for r in rows if r["question_id"] != "tc_dup_001"}
    canonical["tc_dup_001"] = rows[-2]
    meta = {}
    for idx, row in enumerate(rows, start=1):
        row["canonical_row"] = idx
        row["question_sha256"] = question_fingerprint(row["question"])
        meta[row["question_id"]] = {**row}
    shuffled = rows.copy()
  # physical order differs from canonical id order
    shuffled.sort(key=lambda r: (r["difficulty"], r["question_id"]), reverse=True)
    DATA.mkdir(parents=True, exist_ok=True)
    parquet_path = DATA / "trivia_qa_sample.parquet"
    json_path = DATA / "_rows.json"
    json_path.write_text(json.dumps(shuffled), encoding="utf-8")
    sql = f"""
COPY (
  SELECT question_id, question, answer_value, answer_aliases, category, difficulty, source_split
  FROM read_json('{json_path}')
) TO '{parquet_path}' (FORMAT PARQUET);
"""
    subprocess.run([str(DUCKDB), ":memory:", "-c", sql], check=True)
    json_path.unlink(missing_ok=True)
    return meta


def yaml_dump(obj: dict) -> str:
    import yaml

    return yaml.safe_dump(obj, sort_keys=False, allow_unicode=True)


def generate_content(meta: dict[str, dict]) -> None:
    import yaml

    rooms = APP / "content" / "rooms"
    enc = APP / "content" / "encounters"
    scoring = APP / "content" / "scoring"
    cfg = APP / "config"
    for d in (rooms, enc, scoring, cfg):
        d.mkdir(parents=True, exist_ok=True)

    (rooms / "aliases.yaml").write_text(
        """\"on\": foyer
\"old-archive\": archive
\"old-gallery\": gallery
\"observatory-alias\": observatory
""",
        encoding="utf-8",
    )

    room_specs = [
        ("00-foyer.yaml", "foyer", "Foyer", ["archive-history"], {"default": "archive"}),
        ("10-archive.yaml", "archive", "Archive", ["archive-history"], {"default": "old-gallery"}),
        ("20-observatory.yaml", "observatory", "Observatory", ["observatory-science"], {"default": "workshop"}),
        ("30-gallery.yaml", "gallery", "Gallery", ["gallery-literature"], {"default": "workshop"}),
        ("40-workshop.yaml", "workshop", "Workshop", ["workshop-mixed"], {"default": "vault"}),
        ("50-vault.yaml", "vault", "Vault", [], {}),
    ]
    for fname, rid, title, encounters, exits in room_specs:
        doc = {
            "version": "1",
            "id": rid,
            "title": title,
            "encounters": encounters,
            "exits": exits,
        }
        if fname == "00-foyer.yaml":
            doc["encounters"] = ["archive-history", "archive-history"]
        (rooms / fname).write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    tc0008 = meta["tc_0008"]
    tc0015 = meta["tc_0015"]
    tc0007 = meta["tc_0007"]

    (enc / "archive-history.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "1",
                "id": "archive-history",
                "room": "archive",
                "title": "History Gate",
                "trivia": {
                    "row": tc0008["canonical_row"],
                    "question_sha256": "0" * 64,
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (enc / "observatory-science.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "1",
                "id": "observatory-science",
                "room": "workshop",
                "title": "Science Lens",
                "trivia": {"question_id": "tc_dup_001"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (enc / "gallery-literature.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "1",
                "id": "gallery-literature",
                "room": "gallery",
                "title": "Literature Shelf",
                "trivia": {"question_id": "tc_0015"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (enc / "workshop-mixed.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "1",
                "id": "workshop-mixed",
                "room": "workshop",
                "title": "Mixed Bench",
                "trivia": {
                    "row": tc0007["canonical_row"],
                    "question_sha256": tc0007["question_sha256"],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    (scoring / "base.yaml").write_text(
        yaml.safe_dump(
            {"version": "1", "base": {"correct_points": 10, "wrong_points": 0}},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (scoring / "streaks.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "1",
                "streaks": {"bonuses": [{"threshold": 2, "bonus": 5}]},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (scoring / "difficulty.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "1",
                "difficulty": {
                    "tiers": [
                        {"min": 3, "multiplier": 1.5},
                        {"min": 2, "multiplier": 1.2},
                    ]
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    (cfg / "dungeon.toml").write_text(
        """version = "1"

[dungeon]
root = "."
content_dir = "content"
start_room = "on"
exit_room = "vault"
state = ".state/audit-state.json"
output = "/output"
dataset = "/data/trivia_qa_sample.parquet"
contracts = "/data/contracts"
""",
        encoding="utf-8",
    )

    (cfg / "verification-answers.toml").write_text(
        f"""version = "1"

[answers]
archive-history = "{tc0008['answer_value']}"
observatory-science = "alpha"
gallery-literature = "{tc0015['answer_value']}"
workshop-mixed = "  Ankara  "
""",
        encoding="utf-8",
    )

    # Fixed content copies for solution reference
    fixed_dir = TASK / "scripts" / "fixed_content"
    fixed_dir.mkdir(parents=True, exist_ok=True)
    fixed_enc = fixed_dir / "encounters"
    fixed_enc.mkdir(exist_ok=True)
    (fixed_enc / "archive-history.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "1",
                "id": "archive-history",
                "room": "archive",
                "title": "History Gate",
                "trivia": {
                    "row": tc0008["canonical_row"],
                    "question_sha256": tc0008["question_sha256"],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (fixed_enc / "observatory-science.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "1",
                "id": "observatory-science",
                "room": "workshop",
                "title": "Science Lens",
                "trivia": {"question_id": "tc_0020"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    fixed_rooms = fixed_dir / "rooms"
    fixed_rooms.mkdir(exist_ok=True)
    (fixed_rooms / "00-foyer.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "1",
                "id": "foyer",
                "title": "Foyer",
                "encounters": ["archive-history"],
                "exits": {"default": "archive"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (fixed_rooms / "10-archive.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "1",
                "id": "archive",
                "title": "Archive",
                "encounters": ["archive-history"],
                "exits": {"default": "gallery"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (cfg / "verification-answers.toml.fixed").write_text(
        f"""version = "1"

[answers]
archive-history = "{tc0008['answer_value']}"
observatory-science = "{meta['tc_0020']['answer_value']}"
gallery-literature = "{tc0015['answer_value']}"
workshop-mixed = "Ankara"
""",
        encoding="utf-8",
    )
    (fixed_enc / "workshop-mixed.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "1",
                "id": "workshop-mixed",
                "room": "workshop",
                "title": "Mixed Bench",
                "trivia": {
                    "row": tc0007["canonical_row"],
                    "question_sha256": tc0007["question_sha256"],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    shutil.copytree(fixed_dir, TASK / "solution" / "fixed_content", dirs_exist_ok=True)
    (scoring / "difficulty.yaml.fixed").write_text(
        yaml.safe_dump(
            {
                "version": "1",
                "difficulty": {
                    "tiers": [
                        {"min": 2, "multiplier": 1.2},
                        {"min": 3, "multiplier": 1.5},
                    ]
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def generate_fixture_hashes() -> None:
    hashes = {}
    for path in sorted(DATA.glob("**/*")):
        if path.is_file():
            hashes[str(path.relative_to(ENV))] = sha256_file(path)
    for path in sorted(CONTRACTS.glob("*.json")):
        hashes[str(path.relative_to(ENV))] = sha256_file(path)
    write_json(TESTS / "fixture_hashes.json", hashes)


def main() -> None:
    generate_contracts()
    meta = generate_parquet()
    generate_content(meta)
    generate_fixture_hashes()
    print("Generated contracts, parquet, content, fixture hashes")


if __name__ == "__main__":
    main()
