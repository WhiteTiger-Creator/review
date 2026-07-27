"""Behavioral verifier for tag-neighborhood artist classification."""

import csv
import hashlib
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures"
BASE = FIXTURES / "ordered"
CANDIDATE = Path(os.environ.get("CANDIDATE_PATH", "/tmp/artist_country_classifier"))
CLASSES = ("DE", "GB", "US")
QUALITY = {
    "ordered": (0.58, 1.40),
    "permuted": (0.58, 1.40),
    "renamed": (0.58, 1.40),
    "rotated": (0.52, 1.80),
    "type_holdout": (0.45, 1.90),
    "cold_tags": (0.58, 1.40),
}


def _table(path):
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write(path, fieldnames, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _stable(text):
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")


def _ordered(rows, reverse=False):
    return sorted(
        rows,
        key=lambda row: _stable("|".join(str(value) for value in row.values())),
        reverse=reverse,
    )


def _full_labels():
    labels = {
        row["artist_id"]: row["country"] for row in _table(BASE / "train_labels.csv")[1]
    }
    labels.update(
        {
            row["artist_id"]: row["country"]
            for row in _table(FIXTURES / "targets.csv")[1]
        }
    )
    return labels


def _materialize(name):
    artist_header, artists = _table(BASE / "artists.csv")
    tag_header, tags = _table(BASE / "tags.csv")
    edge_header, edges = _table(BASE / "artist_tags.csv")
    labels = _full_labels()
    ids = [row["artist_id"] for row in artists]
    base_queries = {row["artist_id"] for row in _table(BASE / "queries.csv")[1]}

    if name in {"ordered", "permuted", "renamed", "cold_tags"}:
        queries = base_queries
    elif name == "rotated":
        queries = {artist_id for artist_id in ids if _stable(artist_id) % 4 == 1}
    elif name == "type_holdout":
        queries = {
            row["artist_id"] for row in artists if row["artist_type"] == "Person"
        }
    else:
        raise ValueError(name)

    train_ids = [artist_id for artist_id in ids if artist_id not in queries]
    assert queries
    assert {labels[artist_id] for artist_id in train_ids} == set(CLASSES)
    rename = name == "renamed"
    artist_mapping = {
        artist_id: (
            f"artist-{position:04x}-{hashlib.sha256(artist_id.encode()).hexdigest()[:10]}"
            if rename
            else artist_id
        )
        for position, artist_id in enumerate(sorted(ids, key=_stable))
    }
    tag_ids = [row["tag_id"] for row in tags]
    tag_mapping = {
        tag_id: (
            f"tag-{position:04x}-{hashlib.sha256(tag_id.encode()).hexdigest()[:10]}"
            if rename
            else tag_id
        )
        for position, tag_id in enumerate(sorted(tag_ids, key=_stable))
    }
    canonical = {mapped: artist_id for artist_id, mapped in artist_mapping.items()}

    artist_rows = []
    for row in artists:
        out = dict(row)
        out["artist_id"] = artist_mapping[row["artist_id"]]
        artist_rows.append(out)
    tag_rows = [{"tag_id": tag_mapping[row["tag_id"]]} for row in tags]
    edge_rows = [
        {
            "artist_id": artist_mapping[row["artist_id"]],
            "tag_id": tag_mapping[row["tag_id"]],
        }
        for row in edges
    ]

    if name == "cold_tags":
        for artist_id in sorted(queries):
            cold = f"query-only-{hashlib.sha256(artist_id.encode()).hexdigest()[:12]}"
            tag_rows.append({"tag_id": cold})
            edge_rows.append({"artist_id": artist_mapping[artist_id], "tag_id": cold})

    train_rows = [
        {"artist_id": artist_mapping[artist_id], "country": labels[artist_id]}
        for artist_id in train_ids
    ]
    query_rows = [{"artist_id": artist_mapping[artist_id]} for artist_id in queries]
    if name != "ordered":
        artist_rows = _ordered(artist_rows, reverse=True)
        tag_rows = _ordered(tag_rows)
        edge_rows = _ordered(edge_rows, reverse=True)
        train_rows = _ordered(train_rows, reverse=True)
        query_rows = _ordered(query_rows)

    root = Path(tempfile.mkdtemp(prefix=f"artist-{name}-"))
    data = root / "data"
    data.mkdir()
    _write(data / "artists.csv", artist_header, artist_rows)
    _write(data / "tags.csv", tag_header, tag_rows)
    _write(data / "artist_tags.csv", edge_header, edge_rows)
    _write(data / "train_labels.csv", ["artist_id", "country"], train_rows)
    _write(data / "queries.csv", ["artist_id"], query_rows)
    root.chmod(0o755)
    data.chmod(0o755)
    for path in data.iterdir():
        path.chmod(0o644)

    targets = {artist_mapping[artist_id]: labels[artist_id] for artist_id in queries}
    return root, data, targets, canonical


def _tree_digest(path):
    digest = hashlib.sha256()
    for item in sorted(path.iterdir()):
        digest.update(item.name.encode())
        digest.update(item.read_bytes())
    return digest.hexdigest()


def _invoke(data):
    parent = Path(tempfile.mkdtemp(prefix="artist-output-"))
    parent.chmod(0o777)
    output = parent / "output"
    env = dict(os.environ)
    env.update(
        {
            "DATA_PATH": str(data),
            "OUTPUT_PATH": str(output),
            "HOME": "/tmp",
            "TMPDIR": "/tmp",
        }
    )
    proc = subprocess.run(
        [
            "/usr/bin/setpriv",
            "--reuid=65534",
            "--regid=65534",
            "--clear-groups",
            str(CANDIDATE),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=40,
        check=False,
    )
    return parent, output, proc


def _evaluate(name, require_quality=True, mutation=None):
    root, data, targets, canonical = _materialize(name)
    output_parent = None
    try:
        if mutation is not None:
            mutation(data)
        before = _tree_digest(data)
        output_parent, output, proc = _invoke(data)
        assert proc.returncode == 0, proc.stderr
        assert output.is_dir()
        assert sorted(path.name for path in output.iterdir()) == ["predictions.csv"]
        path = output / "predictions.csv"
        raw = path.read_bytes()
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            assert reader.fieldnames == [
                "artist_id",
                "prob_DE",
                "prob_GB",
                "prob_US",
                "predicted_country",
            ]
        assert rows
        assert [row["artist_id"] for row in rows] == sorted(targets)
        assert _tree_digest(data) == before

        correct = {country: [0, 0] for country in set(targets.values())}
        loss = 0.0
        probabilities = {}
        for row in rows:
            artist_id = row["artist_id"]
            values = [float(row[f"prob_{country}"]) for country in CLASSES]
            assert all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in values)
            assert abs(sum(values) - 1.0) <= 1e-8
            best = max(range(3), key=lambda position: (values[position], -position))
            assert row["predicted_country"] == CLASSES[best]
            truth = targets[artist_id]
            correct[truth][1] += 1
            correct[truth][0] += row["predicted_country"] == truth
            loss -= math.log(max(values[CLASSES.index(truth)], 1e-15))
            probabilities[canonical[artist_id]] = values

        balanced = sum(hit / total for hit, total in correct.values()) / len(correct)
        mean_loss = loss / len(rows)
        if require_quality:
            minimum_balanced, maximum_loss = QUALITY[name]
            assert balanced >= minimum_balanced, (name, balanced, mean_loss)
            assert mean_loss <= maximum_loss, (name, balanced, mean_loss)
        return {
            "probabilities": probabilities,
            "raw": raw,
            "balanced": balanced,
            "loss": mean_loss,
        }
    finally:
        shutil.rmtree(root)
        if output_parent is not None:
            shutil.rmtree(output_parent)


def _thin_tag_edges(data):
    path = data / "artist_tags.csv"
    header, rows = _table(path)
    grouped = {}
    for row in rows:
        grouped.setdefault(row["artist_id"], []).append(row)
    kept = []
    for artist_rows in grouped.values():
        kept.append(artist_rows[0])
        kept.extend(
            row for position, row in enumerate(artist_rows[1:], 1) if position % 3
        )
    _write(path, header, kept)


def _append_unknown_artist_edge(data):
    path = data / "artist_tags.csv"
    tag_id = path.read_text().splitlines()[1].split(",")[1]
    with path.open("a") as handle:
        handle.write(f"missing-artist,{tag_id}\n")


def _append_unknown_tag_edge(data):
    path = data / "artist_tags.csv"
    artist_id = path.read_text().splitlines()[1].split(",")[0]
    with path.open("a") as handle:
        handle.write(f"{artist_id},missing-tag\n")


def _append_duplicate_edge(data):
    path = data / "artist_tags.csv"
    first = path.read_text().splitlines()[1]
    with path.open("a") as handle:
        handle.write(first + "\n")


def _duplicate_artist(data):
    path = data / "artists.csv"
    first = path.read_text().splitlines()[1]
    with path.open("a") as handle:
        handle.write(first + "\n")


def _duplicate_tag(data):
    path = data / "tags.csv"
    first = path.read_text().splitlines()[1]
    with path.open("a") as handle:
        handle.write(first + "\n")


def _unknown_query(data):
    with (data / "queries.csv").open("a") as handle:
        handle.write("missing-artist\n")


def _duplicate_query(data):
    path = data / "queries.csv"
    first = path.read_text().splitlines()[1]
    with path.open("a") as handle:
        handle.write(first + "\n")


def _overlap_split(data):
    artist_id = (data / "queries.csv").read_text().splitlines()[1]
    with (data / "train_labels.csv").open("a") as handle:
        handle.write(f"{artist_id},DE\n")


def _remove_training_class(data):
    path = data / "train_labels.csv"
    header, rows = _table(path)
    for row in rows:
        if row["country"] == "GB":
            row["country"] = "DE"
    _write(path, header, rows)


def _remove_query_edges(data):
    query = (data / "queries.csv").read_text().splitlines()[1]
    path = data / "artist_tags.csv"
    header, rows = _table(path)
    _write(path, header, [row for row in rows if row["artist_id"] != query])


def _assert_invalid(mutation):
    root, data, _targets, _canonical = _materialize("ordered")
    output_parent = None
    try:
        mutation(data)
        for path in data.iterdir():
            path.chmod(0o644)
        output_parent, output, proc = _invoke(data)
        assert proc.returncode != 0
        assert not (output / "predictions.csv").exists()
    finally:
        shutil.rmtree(root)
        if output_parent is not None:
            shutil.rmtree(output_parent)


def test_hidden_quality_across_split_type_and_cold_tag_variants():
    """Predictions generalize across hidden splits, artist types, and cold tags."""
    minimum_rows = {"ordered": 42, "rotated": 30, "type_holdout": 50, "cold_tags": 42}
    for name, minimum in minimum_rows.items():
        result = _evaluate(name)
        assert len(result["probabilities"]) >= minimum


def test_order_and_identifier_invariance():
    """CSV order plus opaque artist and tag identifiers preserve probabilities."""
    baseline = _evaluate("ordered")
    for name in ("permuted", "renamed"):
        changed = _evaluate(name)
        assert baseline["probabilities"].keys() == changed["probabilities"].keys()
        for artist_id in baseline["probabilities"]:
            assert (
                max(
                    abs(left - right)
                    for left, right in zip(
                        baseline["probabilities"][artist_id],
                        changed["probabilities"][artist_id],
                    )
                )
                <= 1e-10
            )


def test_tag_neighborhood_is_load_bearing():
    """Thinning disclosed tag evidence changes enough hidden probabilities."""
    baseline = _evaluate("ordered")
    changed = _evaluate("ordered", require_quality=False, mutation=_thin_tag_edges)
    moved = sum(
        max(
            abs(left - right)
            for left, right in zip(
                baseline["probabilities"][artist_id],
                changed["probabilities"][artist_id],
            )
        )
        > 1e-6
        for artist_id in baseline["probabilities"]
    )
    assert moved >= 15


def test_predictions_are_byte_reproducible():
    """Two isolated runs over the same hidden bundle are byte-identical."""
    assert _evaluate("ordered")["raw"] == _evaluate("ordered")["raw"]


@pytest.mark.parametrize(
    "mutation",
    [_append_unknown_artist_edge, _append_unknown_tag_edge, _append_duplicate_edge],
)
def test_malformed_bipartite_edges_are_rejected(mutation):
    """Unknown endpoints and duplicate bipartite edges fail without output."""
    _assert_invalid(mutation)


@pytest.mark.parametrize(
    "mutation",
    [
        _duplicate_artist,
        _duplicate_tag,
        _unknown_query,
        _duplicate_query,
        _overlap_split,
        _remove_training_class,
        _remove_query_edges,
    ],
)
def test_malformed_nodes_tags_and_splits_are_rejected(mutation):
    """Invalid node, tag, class, and split relations fail without predictions."""
    _assert_invalid(mutation)
