"""Independent semantic oracle for the pod-placement feasibility audit.

Reads the authoritative triples with flat single-hop SELECTs only, then
recomputes admission, residency and topology-domain conflict in plain Python.
It never executes the reference query and shares no clause with it.
"""

from pyoxigraph import RdfFormat, Store

NS = "http://ex.org/k8s#"

EXCLUDING_EFFECTS = ("NoSchedule", "NoExecute")
EVICTING_EFFECT = "NoExecute"


def _rows(store, query):
    solutions = store.query(query)
    variables = list(solutions.variables)
    return [tuple(sol[v].value for v in variables) for sol in solutions]


def _store_from_path(nt_path):
    store = Store()
    with open(nt_path, "rb") as fh:
        store.load(fh.read(), format=RdfFormat.N_TRIPLES)
    return store


class Cluster:
    def __init__(self, source):
        store = source if isinstance(source, Store) else _store_from_path(source)
        self._store = store
        p = f"PREFIX : <{NS}>\n"

        self.nodes = {r[0] for r in _rows(store, p + "SELECT ?n { ?n a :Node }")}
        self.pods = {r[0] for r in _rows(store, p + "SELECT ?p { ?p a :Pod }")}

        self.label_kv = {}
        for ident, key, value in _rows(
            store, p + "SELECT ?l ?k ?v { ?l a :Label ; :key ?k ; :value ?v }"
        ):
            self.label_kv[ident] = (key, value)

        self.taint_kve = {}
        for ident, key, value, effect in _rows(
            store,
            p + "SELECT ?t ?k ?v ?e { ?t a :Taint ; :key ?k ; :value ?v ; :effect ?e }",
        ):
            self.taint_kve[ident] = (key, value, effect)

        self.tol_def = {}
        for ident, key, operator, value, effect in _rows(
            store,
            p + "SELECT ?t ?k ?o ?v ?e { ?t a :Toleration ; :key ?k ; :operator ?o ;"
            " :value ?v ; :effect ?e }",
        ):
            self.tol_def[ident] = (key, operator, value, effect)

        self.aa_def = {}
        for ident, selector, topology_key in _rows(
            store,
            p + "SELECT ?a ?s ?k { ?a a :AntiAffinity ; :selectorLabel ?s ;"
            " :topologyKey ?k }",
        ):
            self.aa_def[ident] = (selector, topology_key)

        self.node_labels = self._multimap(store, p, "?n :hasLabel ?x", self.nodes)
        self.node_taints = self._multimap(store, p, "?n :hasTaint ?x", self.nodes)
        self.pod_labels = self._multimap(store, p, "?n :hasPodLabel ?x", self.pods)
        self.pod_tols = self._multimap(store, p, "?n :hasToleration ?x", self.pods)
        self.pod_requires = self._multimap(store, p, "?n :requiresLabel ?x", self.pods)

        self.placed = {}
        for pod, host in _rows(store, p + "SELECT ?p ?n { ?p :placedOn ?n }"):
            self.placed[pod] = host

        self.pod_aa = {}
        for pod, aa in _rows(store, p + "SELECT ?p ?a { ?p :hasAntiAffinity ?a }"):
            self.pod_aa[pod] = self.aa_def[aa]

        self.pending = set()
        for row in _rows(store, p + "SELECT ?p { ?p :pending true }"):
            self.pending.add(row[0])

    def _multimap(self, store, prefix, pattern, keyset):
        out = {k: set() for k in keyset}
        for subject, obj in _rows(store, prefix + f"SELECT ?n ?x {{ {pattern} }}"):
            out.setdefault(subject, set()).add(obj)
        return out

    def matches(self, tol, taint):
        tol_key, operator, tol_value, tol_effect = self.tol_def[tol]
        taint_key, taint_value, taint_effect = self.taint_kve[taint]
        if tol_effect != "" and tol_effect != taint_effect:
            return False
        if tol_key == "" and operator == "Exists":
            return True
        if tol_key != taint_key:
            return False
        if operator == "Exists":
            return True
        return operator == "Equal" and tol_value == taint_value

    def tolerates(self, pod, taint):
        return any(self.matches(t, taint) for t in self.pod_tols.get(pod, ()))

    def excluding_taints(self, node):
        return [
            t
            for t in self.node_taints.get(node, ())
            if self.taint_kve[t][2] in EXCLUDING_EFFECTS
        ]

    def tolerates_node(self, pod, node):
        # The single existential tolerance predicate the naive_any_taint
        # baseline defines once and reuses for both admission and residency.
        relevant = self.excluding_taints(node)
        if not relevant:
            return True
        return any(self.tolerates(pod, t) for t in relevant)

    def admits(self, pod, node):
        for t in self.node_taints.get(node, ()):
            if self.taint_kve[t][2] in EXCLUDING_EFFECTS and not self.tolerates(pod, t):
                return False
        return True

    def resident(self, pod):
        host = self.placed.get(pod)
        if host is None:
            return False
        for t in self.node_taints.get(host, ()):
            if self.taint_kve[t][2] == EVICTING_EFFECT and not self.tolerates(pod, t):
                return False
        return True

    def topo_value(self, node, key):
        for lab in self.node_labels.get(node, ()):
            label_key, label_value = self.label_kv[lab]
            if label_key == key:
                return label_value
        return None

    def selector_matches(self, pod, node):
        needed = self.pod_requires.get(pod, set())
        return needed <= self.node_labels.get(node, set())

    def occupants(self, selector, resident_fn):
        out = []
        for other, host in self.placed.items():
            if selector in self.pod_labels.get(other, ()) and resident_fn(other):
                out.append((other, host))
        return out

    def _conflict(self, pod, node, resident_fn):
        aa = self.pod_aa.get(pod)
        if aa is None:
            return False
        selector, topology_key = aa
        domain = self.topo_value(node, topology_key)
        if domain is None:
            return True
        for _, host in self.occupants(selector, resident_fn):
            if self.topo_value(host, topology_key) == domain:
                return True
        return False

    def feasible(self, pod, node):
        if not self.admits(pod, node):
            return False
        if not self.selector_matches(pod, node):
            return False
        return not self._conflict(pod, node, self.resident)

    def count(self, pod):
        return sum(1 for n in self.nodes if self.feasible(pod, n))

    def rows(self):
        out = set()
        for pod in self.pending:
            c = self.count(pod)
            out.add((pod, "true" if c > 0 else "false", c))
        return out

    def naive_any_taint_resident(self, pod):
        host = self.placed.get(pod)
        if host is None:
            return False
        return self.tolerates_node(pod, host)

    def naive_any_taint_feasible(self, pod, node):
        if not self.tolerates_node(pod, node):
            return False
        if not self.selector_matches(pod, node):
            return False
        return not self._conflict(pod, node, self.naive_any_taint_resident)

    def naive_any_taint_rows(self):
        return self._rows_from(self.naive_any_taint_feasible)

    def naive_ignore_eviction_feasible(self, pod, node):
        if not self.admits(pod, node):
            return False
        if not self.selector_matches(pod, node):
            return False
        return not self._conflict(pod, node, lambda o: o in self.placed)

    def naive_ignore_eviction_rows(self):
        return self._rows_from(self.naive_ignore_eviction_feasible)

    def naive_same_node_only_feasible(self, pod, node):
        if not self.admits(pod, node):
            return False
        if not self.selector_matches(pod, node):
            return False
        aa = self.pod_aa.get(pod)
        if aa is None:
            return True
        selector, _ = aa
        return all(host != node for _, host in self.occupants(selector, self.resident))

    def naive_same_node_only_rows(self):
        return self._rows_from(self.naive_same_node_only_feasible)

    def _rows_from(self, predicate):
        out = set()
        for pod in self.pending:
            c = sum(1 for n in self.nodes if predicate(pod, n))
            out.add((pod, "true" if c > 0 else "false", c))
        return out
