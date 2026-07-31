"""Query execution and result normalization helpers for the verifier.

Candidate query text is never inspected; it is only executed and its rows
compared with the oracle under the task's disclosed contract.
"""

import os

from pyoxigraph import RdfFormat, Store

CONTRACT_COLUMNS = ["pod", "schedulable", "feasible_node_count"]


def load_store(nt_path):
    store = Store()
    with open(nt_path, "rb") as fh:
        store.load(fh.read(), format=RdfFormat.N_TRIPLES)
    return store


def load_store_text(nt_text):
    store = Store()
    store.load(nt_text.encode("utf-8"), format=RdfFormat.N_TRIPLES)
    return store


def read_text(path):
    with open(path) as fh:
        return fh.read()


def run_query(store, query_text):
    solutions = store.query(query_text)
    variables = [v.value for v in solutions.variables]
    rows = []
    for sol in solutions:
        row = []
        for v in solutions.variables:
            term = sol[v]
            row.append(None if term is None else getattr(term, "value", str(term)))
        rows.append(tuple(row))
    return variables, rows


def normalize(variables, rows):
    if list(variables) != CONTRACT_COLUMNS:
        raise ValueError(f"unexpected column set: {variables!r}")
    out = set()
    for row in rows:
        pod, schedulable, count = row
        if pod is None or schedulable is None or count is None:
            raise ValueError(f"unbound term in row: {row!r}")
        out.add((pod, str(schedulable).lower(), int(float(count))))
    return out


def result_set(store, query_text):
    variables, rows = run_query(store, query_text)
    return normalize(variables, rows)


def fixtures_dir():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def read_fixture(name):
    with open(os.path.join(fixtures_dir(), name)) as fh:
        return fh.read()
