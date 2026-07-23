"""Independent expectation model for dataset identity, scoring, and graph simulation."""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb

IssueTuple = tuple[str, str, str]


def _java_character_to_lower_case(text: str) -> str:
    """Per-code-point simple lowercase matching Java ``Character.toLowerCase``.

    Unlike ``str.casefold()`` / full ``str.lower()`` expansions, this keeps a
    1:1 mapping (e.g. ``İ`` U+0130 → ``i`` U+0069, not ``i`` + combining dot).
    """
    parts: list[str] = []
    for ch in text:
        lowered = ch.lower()
        parts.append(lowered if len(lowered) == 1 else lowered[0])
    return "".join(parts)


def question_fingerprint(question: str | None) -> str:
    if question is None:
        text = ""
    else:
        text = _java_character_to_lower_case(unicodedata.normalize("NFC", question))
        stripped = "".join(c if c.isalnum() or c.isspace() else "" for c in text)
        text = " ".join(stripped.split())
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_answer(value: str | None) -> str:
    if value is None:
        return ""
    text = _java_character_to_lower_case(unicodedata.normalize("NFC", value))
    stripped = "".join(c if c.isalnum() or c.isspace() else "" for c in text)
    return " ".join(stripped.split())


def canonical_rows(parquet_path: Path) -> list[dict[str, Any]]:
    conn = duckdb.connect()
    try:
        rows = conn.execute(
            """
            SELECT question_id, question, answer_value, answer_aliases, category, difficulty, source_split
            FROM read_parquet(?)
            ORDER BY question_id ASC
            """,
            [str(parquet_path)],
        ).fetchall()
        columns = [
            "question_id",
            "question",
            "answer_value",
            "answer_aliases",
            "category",
            "difficulty",
            "source_split",
        ]
        result: list[dict[str, Any]] = []
        for index, row in enumerate(rows, start=1):
            record = dict(zip(columns, row))
            record["canonical_row"] = index
            record["question_sha256"] = question_fingerprint(record["question"])
            result.append(record)
        return result
    finally:
        conn.close()


def lookup_by_id(parquet_path: Path, question_id: str) -> tuple[str, dict[str, Any] | None]:
    conn = duckdb.connect()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM read_parquet(?) WHERE question_id = ?",
            [str(parquet_path), question_id],
        ).fetchone()[0]
        if count == 0:
            return "dataset.missing-id", None
        if count > 1:
            return "dataset.ambiguous-id", None
        row = conn.execute(
            """
            SELECT question_id, question, answer_value, answer_aliases, category, difficulty, source_split
            FROM read_parquet(?) WHERE question_id = ?
            """,
            [str(parquet_path), question_id],
        ).fetchone()
        columns = [
            "question_id",
            "question",
            "answer_value",
            "answer_aliases",
            "category",
            "difficulty",
            "source_split",
        ]
        return "ok", dict(zip(columns, row))
    finally:
        conn.close()


def lookup_by_legacy_row(
    parquet_path: Path,
    row: int,
    fingerprint: str,
) -> tuple[str, dict[str, Any] | None]:
    rows = canonical_rows(parquet_path)
    if row < 1 or row > len(rows):
        return "dataset.missing-id", None
    record = rows[row - 1]
    actual = question_fingerprint(record["question"])
    if actual != fingerprint.lower():
        return "dataset.fingerprint-mismatch", None
    return "ok", record


def merge_scoring(documents: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {"version": "1"}
    for doc in documents:
        for key, value in doc.items():
            if key == "version":
                continue
            if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
    return merged


def score_encounter(
    correct: bool,
    difficulty: int,
    streak: int,
    scoring: dict[str, Any],
) -> int:
    base = scoring.get("base", {})
    points = base.get("correct_points", 10) if correct else base.get("wrong_points", 0)
    if not correct:
        return int(points)
    multiplier = 1.0
    tiers = scoring.get("difficulty", {}).get("tiers", [])
    for tier in sorted(tiers, key=lambda item: item["min"]):
        if difficulty >= tier["min"]:
            multiplier = float(tier["multiplier"])
    points = int(round(points * multiplier))
    for bonus in scoring.get("streaks", {}).get("bonuses", []):
        if streak >= bonus["threshold"]:
            points += int(bonus["bonus"])
    return points


def is_answer_correct(given: str | None, expected: str, aliases: list[str] | None) -> bool:
    norm_given = normalize_answer(given)
    if norm_given == normalize_answer(expected):
        return True
    if aliases:
        for alias in aliases:
            if alias is None:
                continue
            if norm_given == normalize_answer(alias):
                return True
    return False


def resolve_room(room_id: str, aliases: dict[str, str]) -> str:
    return aliases.get(room_id, room_id)


@dataclass
class GraphModel:
    rooms: dict[str, dict[str, Any]]
    encounters: dict[str, dict[str, Any]]
    aliases: dict[str, str] = field(default_factory=dict)
    scoring: dict[str, Any] = field(default_factory=dict)
    start_room: str = "foyer"
    exit_room: str = "vault"

    def validate(self, root_prefix: str = "") -> list[IssueTuple]:
        issues: list[IssueTuple] = []
        room_ids = set(self.rooms)
        encounter_ids = set(self.encounters)

        for room_id, room in self.rooms.items():
            rel = _artifact_path(root_prefix, f"bundle/chambers/{room_id}.yaml")
            seen_encounters: set[str] = set()
            for enc_id in room.get("encounters", []):
                if enc_id in seen_encounters:
                    issues.append((rel, "/encounters", "graph.duplicate-encounter"))
                seen_encounters.add(enc_id)
                if enc_id not in encounter_ids:
                    issues.append((rel, "/encounters", "graph.missing-encounter"))
            for pointer, target in room.get("exits", {}).items():
                resolved = resolve_room(target, self.aliases)
                if resolved not in room_ids:
                    issues.append((rel, f"/exits/{pointer}", "graph.unknown-room"))

        for enc_id, enc in self.encounters.items():
            rel = _artifact_path(root_prefix, f"bundle/nodes/{enc_id}.yaml")
            room_name = enc.get("room")
            resolved_room = resolve_room(room_name, self.aliases)
            if resolved_room not in room_ids:
                issues.append((rel, "/room", "graph.unknown-room"))

        cycle_room = self._find_cycle_without_exit()
        if cycle_room:
            rel = _artifact_path(root_prefix, f"bundle/chambers/{cycle_room}.yaml")
            issues.append((rel, "/exits", "graph.cycle"))

        dead_end = self._find_dead_end()
        if dead_end:
            rel = _artifact_path(root_prefix, f"bundle/chambers/{dead_end}.yaml")
            issues.append((rel, "/exits", "graph.dead-end"))

        return sorted(issues)

    def _find_cycle_without_exit(self) -> str | None:
        start = resolve_room(self.start_room, self.aliases)
        if start == self.exit_room:
            return None
        visited: set[str] = set()
        current = start
        while current != self.exit_room:
            if current in visited:
                return current
            visited.add(current)
            room = self.rooms.get(current)
            if room is None:
                return None
            nxt = room.get("exits", {}).get("default")
            if not nxt:
                return None
            current = resolve_room(nxt, self.aliases)
        return None

    def _find_dead_end(self) -> str | None:
        start = resolve_room(self.start_room, self.aliases)
        visited: set[str] = set()
        current = start
        while True:
            if current == self.exit_room:
                return None
            if current in visited:
                return None
            visited.add(current)
            room = self.rooms.get(current)
            if room is None:
                return current
            nxt = room.get("exits", {}).get("default")
            if not nxt:
                return current
            resolved = resolve_room(nxt, self.aliases)
            if resolved not in self.rooms and resolved != self.exit_room:
                return current
            current = resolved


def simulate_playthrough(
    model: GraphModel,
    answers: dict[str, str],
    *,
    parquet_path: Path | None = None,
) -> dict[str, Any]:
    current = resolve_room(model.start_room, model.aliases)
    visited: list[str] = []
    encounters: list[str] = []
    score = 0
    streak = 0
    seen: set[str] = set()

    while True:
        if current in seen and current != model.exit_room:
            return {
                "reached_exit": False,
                "total_score": score,
                "visited_rooms": visited,
                "encounters": encounters,
            }
        seen.add(current)
        visited.append(current)
        if current == model.exit_room:
            break
        room = model.rooms.get(current)
        if room is None:
            break
        for enc_id in room.get("encounters", []):
            enc = model.encounters.get(enc_id)
            if enc is None:
                continue
            encounters.append(enc_id)
            given = answers.get(enc_id)
            question = enc.get("resolved_question") or {}
            correct = is_answer_correct(
                given,
                question.get("answer_value", ""),
                question.get("answer_aliases"),
            )
            if correct:
                streak += 1
            else:
                streak = 0
            difficulty = int(question.get("difficulty", 1))
            score += score_encounter(correct, difficulty, streak, model.scoring)
        nxt = room.get("exits", {}).get("default")
        if not nxt:
            break
        current = resolve_room(nxt, model.aliases)

    return {
        "reached_exit": visited[-1] == model.exit_room if visited else False,
        "total_score": score,
        "visited_rooms": visited,
        "encounters": encounters,
    }


def resolve_encounter_trivia(
    parquet_path: Path,
    trivia: dict[str, Any],
) -> tuple[list[IssueTuple], dict[str, Any] | None]:
    issues: list[IssueTuple] = []
    if "question_id" in trivia:
        code, record = lookup_by_id(parquet_path, trivia["question_id"])
        if code != "ok":
            issues.append(("encounter", "/trivia/question_id", code))
            return issues, None
        return issues, record
    row = int(trivia["row"])
    fp = trivia["question_sha256"]
    code, record = lookup_by_legacy_row(parquet_path, row, fp)
    if code != "ok":
        pointer = "/trivia/question_sha256" if code == "dataset.fingerprint-mismatch" else "/trivia/row"
        issues.append(("encounter", pointer, code))
        return issues, None
    return issues, record


def content_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dataset_digest(path: Path) -> str:
    return content_sha256(path)


def _artifact_path(root_prefix: str, suffix: str) -> str:
    if root_prefix:
        return f"{root_prefix.rstrip('/')}/{suffix}"
    return suffix


def expected_artifact_list(root: Path, config_path: Path) -> list[str]:
    """Return lexicographically sorted relative artifact paths under *root*."""
    paths: list[str] = []
    for pattern in ("bundle/chambers", "bundle/nodes", "bundle/weights"):
        base = root / pattern
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix.lower() in {".yaml", ".yml", ".toml"}:
                paths.append(path.relative_to(root).as_posix())
    if config_path.is_file():
        paths.append(config_path.relative_to(root).as_posix())
    return sorted(set(paths))


def merge_json_documents(paths: list[Path]) -> list[dict[str, Any]]:
    import yaml

    docs: list[dict[str, Any]] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".toml":
            import tomllib

            docs.append(tomllib.loads(text))
        else:
            docs.append(yaml.safe_load(text))
    return docs
