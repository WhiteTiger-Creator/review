import os
import sys

from pyoxigraph import RdfFormat, Store


def main(argv):
    query_path = argv[1] if len(argv) > 1 else "/app/answer.sparql"
    graph_path = os.environ.get("CLUSTER_GRAPH", "/app/graph/cluster.nt")
    with open(query_path) as fh:
        query_text = fh.read()
    store = Store()
    with open(graph_path, "rb") as fh:
        store.load(fh.read(), format=RdfFormat.N_TRIPLES)
    solutions = store.query(query_text)
    variables = [v.value for v in solutions.variables]
    print("\t".join(variables))
    count = 0
    for sol in solutions:
        cells = []
        for v in solutions.variables:
            term = sol[v]
            cells.append("" if term is None else getattr(term, "value", str(term)))
        print("\t".join(cells))
        count += 1
    print(f"({count} rows)", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv)
