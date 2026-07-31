import os
import subprocess
import sys
import tarfile
import tempfile

import pytest
from oracle import compute_reference

APP = os.environ.get("PT_APP", "/app")
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(TESTS_DIR, "fixtures")
ANSWER_PATH = os.path.join(APP, "answer.cypher")
VISIBLE_GRAPH = os.path.join(APP, "graph", "timesync.kuzu")
REQUIRED_COLUMNS = (
    "client",
    "stratum",
    "system_peer",
    "truechimer_count",
    "falseticker_count",
)

# The verifier executes candidate queries through this tests-owned runner rather
# than any binary under the agent-writable /app tree, so the submitted answer is
# graded against the frozen graphs and cannot be steered by tampering with the
# in-container tooling. The query runs in a child process with a wall-clock
# kill-timeout so a pathological query cannot stall the whole verifier.
_RUNNER = r"""
import sys
import kuzu

graph_path = sys.argv[1]
query_text = sys.argv[2]
db = kuzu.Database(graph_path, read_only=True)
conn = kuzu.Connection(db)
result = conn.execute(query_text)
columns = result.get_column_names()
sys.stdout.write("\t".join(columns) + "\n")
while result.has_next():
    row = result.get_next()
    sys.stdout.write(
        "\t".join("" if v is None else str(v) for v in row) + "\n"
    )
"""

_HIDDEN_DIR = tempfile.mkdtemp(prefix="hidden_graph_")


def _extract_hidden():
    with tarfile.open(os.path.join(FIX, "hidden_graph.tar.gz"), "r:gz") as tar:
        tar.extractall(_HIDDEN_DIR)
    return os.path.join(_HIDDEN_DIR, "hidden_graph.kuzu")


HIDDEN_GRAPH = _extract_hidden()


def run_query(query_text, graph_path, timeout=120):
    proc = subprocess.run(
        [sys.executable, "-c", _RUNNER, graph_path, query_text],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        return None, None, proc.stderr
    lines = proc.stdout.split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    if not lines:
        return [], set(), proc.stderr
    columns = lines[0].split("\t")
    rows = {tuple(line.split("\t")) for line in lines[1:]}
    return columns, rows, proc.stderr


def normalize_rows(columns, rows, required=REQUIRED_COLUMNS):
    missing = set(required) - set(columns)
    if missing:
        raise AssertionError(f"query result is missing columns: {missing}")
    idx = [columns.index(c) for c in required]
    return {tuple(row[i] for i in idx) for row in rows}


def _fixture_text(name):
    with open(os.path.join(FIX, name)) as fh:
        return fh.read()


@pytest.fixture(scope="session")
def answer_text():
    assert os.path.exists(ANSWER_PATH), "/app/answer.cypher was not written"
    with open(ANSWER_PATH) as fh:
        text = fh.read()
    assert text.strip(), "/app/answer.cypher is empty"
    return text


@pytest.fixture(scope="session")
def reference_text():
    return _fixture_text("reference_query.cypher")


@pytest.fixture(scope="session")
def naive_overlap_text():
    return _fixture_text("naive_overlap.cypher")


@pytest.fixture(scope="session")
def naive_f_zero_text():
    return _fixture_text("naive_f_zero.cypher")


@pytest.fixture(scope="session")
def naive_fixed_majority_text():
    return _fixture_text("naive_fixed_majority.cypher")


@pytest.fixture(scope="session")
def naive_all_candidates_text():
    return _fixture_text("naive_all_candidates.cypher")


@pytest.fixture(scope="session")
def naive_dispersion_peer_text():
    return _fixture_text("naive_dispersion_peer.cypher")


@pytest.fixture(scope="session")
def literal_list_text():
    return _fixture_text("literal_list.cypher")


@pytest.fixture(scope="session")
def visible_reference():
    return compute_reference(VISIBLE_GRAPH)


@pytest.fixture(scope="session")
def hidden_reference():
    return compute_reference(HIDDEN_GRAPH)


@pytest.fixture(scope="session")
def reference_visible_normalized(reference_text):
    columns, rows, err = run_query(reference_text, VISIBLE_GRAPH)
    assert rows is not None, f"reference query failed on the visible graph: {err}"
    return normalize_rows(columns, rows)


@pytest.fixture(scope="session")
def reference_hidden_normalized(reference_text):
    columns, rows, err = run_query(reference_text, HIDDEN_GRAPH)
    assert rows is not None, f"reference query failed on the hidden graph: {err}"
    return normalize_rows(columns, rows)


@pytest.fixture(scope="session")
def answer_visible_raw(answer_text):
    return run_query(answer_text, VISIBLE_GRAPH)


@pytest.fixture(scope="session")
def answer_hidden_raw(answer_text):
    return run_query(answer_text, HIDDEN_GRAPH)


@pytest.fixture(scope="session")
def answer_visible_normalized(answer_visible_raw):
    columns, rows, err = answer_visible_raw
    assert rows is not None, f"answer query failed on the visible graph: {err}"
    return normalize_rows(columns, rows)


@pytest.fixture(scope="session")
def answer_hidden_normalized(answer_hidden_raw):
    columns, rows, err = answer_hidden_raw
    assert rows is not None, f"answer query failed on the hidden graph: {err}"
    return normalize_rows(columns, rows)
