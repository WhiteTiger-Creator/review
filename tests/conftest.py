import atexit
import os
import shutil
import subprocess
import tarfile
import tempfile

import pytest
from lacp_oracle import compute_reference

APP = os.environ.get("PT_APP", "/app")
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(TESTS_DIR, "fixtures")
ANSWER_PATH = os.path.join(APP, "answer.cypher")
RUNNER = os.path.join(APP, "bin", "run_query.py")
VISIBLE_GRAPH = os.path.join(APP, "graph", "lacp_fabric.kuzu")
REQUIRED_COLUMNS = ("switch", "port", "state", "lag_id")
HIDDEN_FAMILIES = ("hidden_a", "hidden_b", "hidden_c")

# The hidden fabrics ship as one archive: an uncompressed Kuzu directory is
# mostly empty pages and balloons the committed task tree.
_HIDDEN_ROOT = tempfile.mkdtemp(prefix="lacp_hidden_")
atexit.register(shutil.rmtree, _HIDDEN_ROOT, True)
with tarfile.open(os.path.join(FIX, "hidden_graph.tar.gz")) as _tf:
    _tf.extractall(_HIDDEN_ROOT, filter="data")


def hidden_graph(family):
    return os.path.join(_HIDDEN_ROOT, "hidden_graph", family, "lacp_fabric.kuzu")


def run_query(query_text, graph_path, timeout=120):
    env = dict(os.environ)
    env["GRAPH_DB_PATH"] = graph_path
    proc = subprocess.run(
        ["python3", RUNNER, query_text],
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        return None, None, proc.stderr
    lines = proc.stdout.split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    if not lines:
        return [], [], proc.stderr
    columns = lines[0].split("\t")
    rows = [tuple(line.split("\t")) for line in lines[1:]]
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
def naive_trust_advertised_partner_text():
    return _fixture_text("naive_trust_advertised_partner.query")


@pytest.fixture(scope="session")
def naive_group_by_actor_key_only_text():
    return _fixture_text("naive_group_by_actor_key_only.query")


@pytest.fixture(scope="session")
def naive_ignore_minlinks_text():
    return _fixture_text("naive_ignore_minlinks.query")


@pytest.fixture(scope="session")
def literal_list_text():
    return _fixture_text("literal_list.query")


# Ground truth is recomputed independently from the raw rows of each graph, not
# by running the reference Cypher, so a blind spot shared between the reference
# query and a candidate query cannot let a wrong answer through.
@pytest.fixture(scope="session")
def visible_reference():
    return compute_reference(VISIBLE_GRAPH)


@pytest.fixture(scope="session")
def hidden_references():
    return {f: compute_reference(hidden_graph(f)) for f in HIDDEN_FAMILIES}


@pytest.fixture(scope="session")
def answer_visible_raw(answer_text):
    return run_query(answer_text, VISIBLE_GRAPH)


@pytest.fixture(scope="session")
def answer_visible_normalized(answer_visible_raw):
    columns, rows, err = answer_visible_raw
    assert rows is not None, f"answer query failed on the visible graph: {err}"
    return normalize_rows(columns, rows)


@pytest.fixture(scope="session")
def answer_hidden_normalized(answer_text):
    out = {}
    for family in HIDDEN_FAMILIES:
        columns, rows, err = run_query(answer_text, hidden_graph(family))
        assert rows is not None, f"answer query failed on {family}: {err}"
        out[family] = normalize_rows(columns, rows)
    return out
