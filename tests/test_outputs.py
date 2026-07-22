import math
import os
import re
import subprocess
from pathlib import Path

import pytest


BIN = Path("/app/bin/fmctl")
TRAIN = Path("/app/fixtures/ctr-train.fm")
EVAL = Path("/app/fixtures/ctr-eval.fm")
HIDDEN = Path("/opt/verifier-fixtures/hidden-train.fm")
TIES = Path("/opt/verifier-fixtures/tie-eval.fm")
MASK = (1 << 64) - 1


def run(*args: str, env: dict[str, str] | None = None, ok: bool = True):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    proc = subprocess.run(
        [str(BIN), *map(str, args)],
        text=True,
        capture_output=True,
        env=merged,
        check=False,
    )
    if ok:
        assert proc.returncode == 0, proc.stderr
    else:
        assert proc.returncode != 0
    return proc


def rows(path: Path):
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        feats: dict[str, float] = {}
        for token in fields[1:]:
            name, raw = token.split(":", 1)
            feats[name] = feats.get(name, 0.0) + float(raw)
        result.append((float(fields[0]), feats))
    return result


def mix(value: int):
    value ^= value >> 30
    value = (value * 0xBF58476D1CE4E5B9) & MASK
    value ^= value >> 27
    value = (value * 0x94D049BB133111EB) & MASK
    return (value ^ (value >> 31)) & MASK


def initial(seed: int, i: int, f: int):
    stream = (
        seed
        ^ (((i + 1) * 0x9E3779B97F4A7C15) & MASK)
        ^ (((f + 1) * 0xBF58476D1CE4E5B9) & MASK)
    )
    unit = (mix(stream) >> 11) / float(1 << 53)
    return 0.05 * (2.0 * unit - 1.0)


def probability(model, feats):
    score = model["bias"]
    for name, value in feats.items():
        if name in model["features"]:
            score += model["features"][name]["linear"] * value
    for f in range(model["factors"]):
        total = squares = 0.0
        for name, value in feats.items():
            if name in model["features"]:
                vx = model["features"][name]["latent"][f] * value
                total += vx
                squares += vx * vx
        score += 0.5 * (total * total - squares)
    score = max(-35.0, min(35.0, score))
    return 1.0 / (1.0 + math.exp(-score))


def reference_train(path: Path, factors=3, epochs=4, batch=2, lr=0.08, l2=0.01, seed=17):
    data = rows(path)
    names = sorted({name for _, feats in data for name in feats})
    model = {
        "factors": factors,
        "bias": 0.0,
        "features": {
            name: {
                "linear": 0.0,
                "latent": [initial(seed, i, f) for f in range(factors)],
            }
            for i, name in enumerate(names)
        },
    }
    order = list(range(len(data)))
    for epoch in range(epochs):
        state = seed ^ (((epoch + 1) * 0x94D049BB133111EB) & MASK)
        for i in range(len(order) - 1, 0, -1):
            state = mix(state)
            j = state % (i + 1)
            order[i], order[j] = order[j], order[i]
        rate = lr / (1.0 + 0.1 * epoch)
        for start in range(0, len(order), batch):
            indices = order[start : start + batch]
            bg = 0.0
            lg = {name: 0.0 for name in names}
            vg = {name: [0.0] * factors for name in names}
            for idx in indices:
                label, feats = data[idx]
                g = probability(model, feats) - label
                bg += g
                sums = [
                    sum(
                        model["features"][name]["latent"][f] * value
                        for name, value in feats.items()
                        if name in model["features"]
                    )
                    for f in range(factors)
                ]
                for name in names:
                    w = model["features"][name]
                    value = feats.get(name, 0.0)
                    lg[name] += g * value + l2 * w["linear"]
                    for f in range(factors):
                        vg[name][f] += (
                            g * value * (sums[f] - w["latent"][f] * value)
                            + l2 * w["latent"][f]
                        )
            scale = rate / len(indices)
            model["bias"] -= scale * bg
            for name in names:
                model["features"][name]["linear"] -= scale * lg[name]
                for f in range(factors):
                    model["features"][name]["latent"][f] -= scale * vg[name][f]
    return model


def parse_model(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    factors = int(lines[1].split()[1])
    model = {"factors": factors, "bias": float(lines[2].split()[1]), "features": {}}
    for line in lines[3:]:
        fields = line.split()
        model["features"][fields[1]] = {
            "linear": float(fields[2]),
            "latent": [float(x) for x in fields[3:]],
        }
    return model


def train(path: Path, output: Path, **overrides):
    values = dict(factors=3, epochs=4, batch=2, lr=0.08, l2=0.01, seed=17)
    values.update(overrides)
    run(
        "train",
        "--data",
        str(path),
        "--model",
        str(output),
        "--factors",
        str(values["factors"]),
        "--epochs",
        str(values["epochs"]),
        "--batch",
        str(values["batch"]),
        "--lr",
        str(values["lr"]),
        "--l2",
        str(values["l2"]),
        "--seed",
        str(values["seed"]),
    )


@pytest.fixture()
def trained(tmp_path):
    model = tmp_path / "model.fm"
    train(TRAIN, model)
    return model


def assert_models_close(actual, expected):
    assert actual["factors"] == expected["factors"]
    assert actual["bias"] == pytest.approx(expected["bias"], abs=2e-15)
    assert actual["features"].keys() == expected["features"].keys()
    for name in actual["features"]:
        assert actual["features"][name]["linear"] == pytest.approx(
            expected["features"][name]["linear"], abs=2e-15
        )
        assert actual["features"][name]["latent"] == pytest.approx(
            expected["features"][name]["latent"], abs=2e-15
        )


def test_binary_rebuilt_from_rust():
    """The fmctl binary rebuilt from Rust sources exists and is executable."""
    assert BIN.is_file() and os.access(BIN, os.X_OK)


def test_exact_bias_after_seeded_minibatches(trained):
    """A trained model matches the independent reference trainer exactly."""
    assert_models_close(parse_model(trained), reference_train(TRAIN))


def test_linear_weights_include_l2_without_bias_regularization(trained):
    """Linear weights carry L2 decay while the bias stays unregularized."""
    actual = parse_model(trained)
    expected = reference_train(TRAIN)
    for name in actual["features"]:
        assert actual["features"][name]["linear"] == pytest.approx(
            expected["features"][name]["linear"], abs=2e-15
        )


def test_latent_gradient_self_term(trained):
    """Latent factors match the reference update that subtracts the self-term."""
    actual = parse_model(trained)
    expected = reference_train(TRAIN)
    for name in actual["features"]:
        assert actual["features"][name]["latent"] == pytest.approx(
            expected["features"][name]["latent"], abs=2e-15
        )


def test_model_features_are_canonically_sorted(trained):
    """Persisted feature records appear in canonical lexicographic order."""
    names = [line.split()[1] for line in trained.read_text().splitlines()[3:]]
    assert names == sorted(names)


def test_model_uses_fixed_seventeen_decimal_fields(trained):
    """Every persisted weight uses the fixed seventeen-decimal encoding."""
    for line in trained.read_text().splitlines()[2:]:
        for token in line.split()[1 if line.startswith("bias") else 2 :]:
            assert re.fullmatch(r"-?\d+\.\d{17}", token)


def test_retraining_is_byte_identical(tmp_path):
    """Retraining with identical arguments produces byte-identical model files."""
    first, second = tmp_path / "a.fm", tmp_path / "b.fm"
    train(TRAIN, first)
    train(TRAIN, second)
    assert first.read_bytes() == second.read_bytes()


def test_training_snapshot_survives_source_data_removal(tmp_path):
    """Prediction works from the persisted snapshot after the training data is gone."""
    copied = tmp_path / "source.fm"
    copied.write_bytes(TRAIN.read_bytes())
    snapshot = tmp_path / "snapshot.fm"
    train(copied, snapshot)
    copied.unlink()
    output = tmp_path / "pred.txt"
    run("predict", "--data", str(EVAL), "--model", str(snapshot), "--output", str(output))
    assert len(output.read_text().splitlines()) == len(rows(EVAL))


def test_seed_changes_latent_state(tmp_path):
    """Changing the seed changes the persisted latent initialization."""
    first, second = tmp_path / "a.fm", tmp_path / "b.fm"
    train(TRAIN, first, seed=17)
    train(TRAIN, second, seed=19)
    assert first.read_bytes() != second.read_bytes()


def test_prediction_probabilities_match_reference(trained, tmp_path):
    """Predicted probabilities include the pairwise interaction contribution."""
    output = tmp_path / "pred.txt"
    run("predict", "--data", str(EVAL), "--model", str(trained), "--output", str(output))
    expected = [probability(parse_model(trained), feats) for _, feats in rows(EVAL)]
    assert [float(x) for x in output.read_text().splitlines()] == pytest.approx(
        expected, abs=5e-13
    )


def test_prediction_ignores_unseen_features(trained, tmp_path):
    """Features absent from the model contribute nothing to the score."""
    data = tmp_path / "unknown.fm"
    data.write_text("1 unknown_only:999\n", encoding="utf-8")
    output = tmp_path / "pred.txt"
    run("predict", "--data", str(data), "--model", str(trained), "--output", str(output))
    expected = 1.0 / (1.0 + math.exp(-parse_model(trained)["bias"]))
    assert float(output.read_text()) == pytest.approx(expected, abs=5e-13)


def test_duplicate_feature_values_accumulate(trained, tmp_path):
    """Repeated feature names in one row accumulate before scoring."""
    a, b = tmp_path / "a.fm", tmp_path / "b.fm"
    a.write_text("1 device_mobile:0.25 device_mobile:0.75\n", encoding="utf-8")
    b.write_text("1 device_mobile:1\n", encoding="utf-8")
    oa, ob = tmp_path / "a.txt", tmp_path / "b.txt"
    run("predict", "--data", str(a), "--model", str(trained), "--output", str(oa))
    run("predict", "--data", str(b), "--model", str(trained), "--output", str(ob))
    assert oa.read_bytes() == ob.read_bytes()


def parse_metrics(path: Path):
    return {line.split()[0]: line.split()[1] for line in path.read_text().splitlines()}


def test_evaluate_logloss_recomputed(trained, tmp_path):
    """Reported log-loss matches the clamped reference computation."""
    output = tmp_path / "metrics.txt"
    run("evaluate", "--data", str(EVAL), "--model", str(trained), "--output", str(output))
    probs = [probability(parse_model(trained), feats) for _, feats in rows(EVAL)]
    labels = [label for label, _ in rows(EVAL)]
    expected = sum(
        -y * math.log(max(1e-15, min(1 - 1e-15, p)))
        - (1 - y) * math.log(1 - max(1e-15, min(1 - 1e-15, p)))
        for y, p in zip(labels, probs)
    ) / len(labels)
    assert float(parse_metrics(output)["logloss"]) == pytest.approx(expected, abs=5e-13)


def reference_auc(pairs):
    pairs = sorted(pairs)
    rank_sum = 0.0
    start = 0
    while start < len(pairs):
        end = start + 1
        while end < len(pairs) and pairs[end][0] == pairs[start][0]:
            end += 1
        rank_sum += sum(y for _, y in pairs[start:end]) * ((start + 1 + end) / 2)
        start = end
    pos = sum(y for _, y in pairs)
    neg = len(pairs) - pos
    return 0.0 if not pos or not neg else (rank_sum - pos * (pos + 1) / 2) / (pos * neg)


def test_evaluate_auc_recomputed(trained, tmp_path):
    """Reported AUC matches the rank-based reference on held-out data."""
    output = tmp_path / "metrics.txt"
    run("evaluate", "--data", str(EVAL), "--model", str(trained), "--output", str(output))
    pairs = [(probability(parse_model(trained), feats), y) for y, feats in rows(EVAL)]
    assert float(parse_metrics(output)["auc"]) == pytest.approx(reference_auc(pairs), abs=5e-13)


def test_evaluate_confusion_counts(trained, tmp_path):
    """Confusion counts follow the 0.5 probability threshold."""
    output = tmp_path / "metrics.txt"
    run("evaluate", "--data", str(EVAL), "--model", str(trained), "--output", str(output))
    m = parse_metrics(output)
    pairs = [(probability(parse_model(trained), feats) >= 0.5, y == 1) for y, feats in rows(EVAL)]
    assert int(m["tp"]) == sum(pred and label for pred, label in pairs)
    assert int(m["tn"]) == sum(not pred and not label for pred, label in pairs)
    assert int(m["fp"]) == sum(pred and not label for pred, label in pairs)
    assert int(m["fn"]) == sum(not pred and label for pred, label in pairs)


def test_hidden_auc_average_rank_ties(trained, tmp_path):
    """Tied scores on a hidden dataset receive average ranks in AUC."""
    output = tmp_path / "ties.txt"
    run("evaluate", "--data", str(TIES), "--model", str(trained), "--output", str(output))
    assert float(parse_metrics(output)["auc"]) == pytest.approx(0.5)


def test_hidden_dataset_exact_training(tmp_path):
    """Training on a hidden dataset with new hyperparameters matches the reference."""
    model = tmp_path / "hidden.fm"
    train(HIDDEN, model, factors=4, epochs=3, batch=3, lr=0.05, l2=0.02, seed=41)
    expected = reference_train(HIDDEN, factors=4, epochs=3, batch=3, lr=0.05, l2=0.02, seed=41)
    assert_models_close(parse_model(model), expected)


def test_absolute_tb3_data_override(tmp_path):
    """An absolute TB3_FM_DATA path replaces the train data argument."""
    model = tmp_path / "override.fm"
    env = {"TB3_FM_DATA": str(HIDDEN)}
    run(
        "train", "--data", str(TRAIN), "--model", str(model), "--factors", "2",
        "--epochs", "2", "--batch", "2", "--lr", "0.05", "--l2", "0.01",
        "--seed", "9", env=env,
    )
    assert set(parse_model(model)["features"]) == {name for _, feats in rows(HIDDEN) for name in feats}


def test_relative_tb3_data_override_is_ignored(tmp_path):
    """A relative TB3_FM_DATA value is ignored and the train argument is used."""
    model = tmp_path / "relative.fm"
    env = {"TB3_FM_DATA": "relative-hidden.fm"}
    run(
        "train", "--data", str(TRAIN), "--model", str(model), "--factors", "2",
        "--epochs", "1", "--batch", "2", "--lr", "0.05", "--l2", "0.01",
        "--seed", "9", env=env,
    )
    assert "device_mobile" in parse_model(model)["features"]


def test_predict_ignores_tb3_data_override(trained, tmp_path):
    """TB3_FM_DATA only affects train; predict always reads its data argument."""
    with_env, without_env = tmp_path / "a.txt", tmp_path / "b.txt"
    run(
        "predict", "--data", str(EVAL), "--model", str(trained),
        "--output", str(with_env), env={"TB3_FM_DATA": str(HIDDEN)},
    )
    run("predict", "--data", str(EVAL), "--model", str(trained), "--output", str(without_env))
    assert with_env.read_bytes() == without_env.read_bytes()
    assert len(with_env.read_text().splitlines()) == len(rows(EVAL))


def test_malformed_training_row_fails(tmp_path):
    """Rows without feature:value tokens abort training with a nonzero exit."""
    data = tmp_path / "bad.fm"
    data.write_text("1 broken\n", encoding="utf-8")
    run(
        "train", "--data", str(data), "--model", str(tmp_path / "m.fm"),
        "--factors", "2", "--epochs", "1", "--batch", "1", "--lr", "0.1",
        "--l2", "0.0", "--seed", "1", ok=False,
    )


def test_zero_batch_is_rejected(tmp_path):
    """A zero mini-batch size is rejected with a nonzero exit."""
    run(
        "train", "--data", str(TRAIN), "--model", str(tmp_path / "m.fm"),
        "--factors", "2", "--epochs", "1", "--batch", "0", "--lr", "0.1",
        "--l2", "0.0", "--seed", "1", ok=False,
    )


def test_corrupt_duplicate_model_feature_is_rejected(trained, tmp_path):
    """A model file with a duplicated feature record fails to load."""
    bad = tmp_path / "bad.fm"
    lines = trained.read_text().splitlines()
    bad.write_text("\n".join(lines + [lines[3]]) + "\n", encoding="utf-8")
    run(
        "predict", "--data", str(EVAL), "--model", str(bad),
        "--output", str(tmp_path / "p.txt"), ok=False,
    )
