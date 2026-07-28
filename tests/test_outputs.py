import json
import math
import subprocess
import tempfile
from pathlib import Path

BIN = Path("/app/task_file/branch")


def train_predict(train: str, predict: str, depth=3, leaf=0.5):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "train.tsv").write_text(train, encoding="utf-8")
        (root / "predict.tsv").write_text(predict, encoding="utf-8")
        (root / "config.tsv").write_text(
            f"max_depth\t{depth}\nmin_leaf_weight\t{leaf}\n", encoding="utf-8"
        )
        proc = subprocess.run(
            [str(BIN), str(root / "train.tsv"), str(root / "predict.tsv"), str(root / "config.tsv")],
            check=True,
            capture_output=True,
            text=True,
            timeout=8,
        )
        result = json.loads(proc.stdout)
        assert set(result) == {"predictions"}
        for item in result["predictions"]:
            assert set(item) == {"id", "label", "probability"}
            assert math.isfinite(item["probability"])
        return result["predictions"]


class TestFractionalWeightedInduction:
    def test_single_class_distribution_is_exact(self):
        """A pure weighted population remains a probability-one leaf."""
        train = "id\tx\tlabel\tweight\na\t?\tonly\t2\nb\t4\tonly\t3\n"
        assert train_predict(train, "id\tx\nq\t?\n", depth=4) == [
            {"id": "q", "label": "only", "probability": 1.0}
        ]


def test_weight_changes_selected_leaf_label():
    """Sample weights, rather than row counts, determine a terminal prediction."""
    train = "id\tx\tlabel\tweight\na\t1\tred\t1\nb\t2\tblue\t4\nc\t3\tred\t1\n"
    pred = train_predict(train, "id\tx\np\t2\n", depth=0)
    assert pred == [{"id": "p", "label": "blue", "probability": 0.666667}]


def test_best_split_and_recursive_partitioning():
    """Midpoint search and recursive weighted Gini partition a nontrivial pattern."""
    train = "id\tx\ty\tlabel\tweight\na\t0\t0\tno\t1\nb\t0\t1\tyes\t1\nc\t1\t0\tyes\t1\nd\t1\t1\tno\t1\ne\t2\t0\tyes\t3\nf\t2\t1\tyes\t3\n"
    query = "id\tx\ty\nq1\t0\t0\nq2\t1\t1\nq3\t2\t1\n"
    got = train_predict(train, query, depth=3)
    assert [x["label"] for x in got] == ["no", "no", "yes"]
    assert [x["probability"] for x in got] == [0.5, 0.5, 1.0]


def test_missing_training_mass_and_missing_inference_mix():
    """Missing values are fractionally routed in training and probabilistically mixed at inference."""
    train = "id\tx\tlabel\tweight\na\t0\tleft\t3\nb\t10\tright\t1\nc\t?\tright\t4\n"
    got = train_predict(train, "id\tx\nlo\t0\nhi\t10\nmiss\t?\n", depth=1, leaf=1)
    assert [x["label"] for x in got] == ["left", "right", "right"]
    assert got[0]["probability"] == 0.5
    assert got[1]["probability"] == 1.0
    assert got[2]["probability"] == 0.625


def test_lexical_ties_are_deterministic():
    """Class and feature ties follow the declared lexical ordering."""
    train = "id\tb\ta\tlabel\tweight\nr1\t0\t0\tzeta\t1\nr2\t1\t1\talpha\t1\n"
    got = train_predict(train, "id\tb\ta\nq\t0\t1\n", depth=1)
    assert got == [{"id": "q", "label": "alpha", "probability": 1.0}]


def test_invalid_weight_fails():
    """Nonpositive sample weights cause a nonzero process result."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "t").write_text("id\tx\tlabel\tweight\na\t1\tx\t0\n", encoding="utf-8")
        (root / "p").write_text("id\tx\nq\t1\n", encoding="utf-8")
        (root / "c").write_text("max_depth\t1\nmin_leaf_weight\t1\n", encoding="utf-8")
        proc = subprocess.run([str(BIN), str(root / "t"), str(root / "p"), str(root / "c")], check=False)
        assert proc.returncode != 0
