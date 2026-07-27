import os
from fractions import Fraction

VARIANTS = ("pinned", "nodebase", "fwdonly", "nonneg", "leftfall")

MISSING = -1


def read_tables(data_dir):
    out = {}
    for name in sorted(os.listdir(data_dir)):
        if not name.endswith(".csv"):
            continue
        with open(os.path.join(data_dir, name), encoding="utf-8") as fh:
            lines = [ln.strip() for ln in fh if ln.strip() != ""]
        rows = []
        for line in lines[1:]:
            cells = [int(c) for c in line.split(",")]
            rows.append((tuple(cells[:-1]), cells[-1]))
        out[name[:-4]] = rows
    return out


def gini(rows, subset, classes):
    if not subset:
        return Fraction(0)
    counts = [0] * classes
    for i in subset:
        counts[rows[i][1]] += 1
    n = len(subset)
    acc = Fraction(0)
    for c in counts:
        acc += Fraction(c * c, n * n)
    return Fraction(1) - acc


def majority(rows, subset, classes):
    counts = [0] * classes
    for i in subset:
        counts[rows[i][1]] += 1
    best = 0
    for c in range(1, classes):
        if counts[c] > counts[best]:
            best = c
    return best


def best_split(rows, subset, features, classes):
    best = None
    for j in range(features):
        observed = [i for i in subset if rows[i][0][j] != MISSING]
        if len(observed) < 2:
            continue
        values = sorted({rows[i][0][j] for i in observed})
        if len(values) < 2:
            continue
        parent = gini(rows, observed, classes)
        total = len(observed)
        for t in values[:-1]:
            left = [i for i in observed if rows[i][0][j] <= t]
            right = [i for i in observed if rows[i][0][j] > t]
            gain = (
                parent
                - Fraction(len(left), total) * gini(rows, left, classes)
                - Fraction(len(right), total) * gini(rows, right, classes)
            )
            key = (-gain, j, t)
            if best is None or key < best[0]:
                best = (key, j, t, gain)
    if best is None:
        return None
    return best[1], best[2], best[3]


def surrogates(rows, subset, features, jstar, tstar, variant):
    found = []
    for k in range(features):
        if k == jstar:
            continue
        if variant == "nodebase":
            pool = [i for i in subset if rows[i][0][k] != MISSING]
        else:
            pool = [
                i
                for i in subset
                if rows[i][0][k] != MISSING and rows[i][0][jstar] != MISSING
            ]
        if not pool:
            continue
        goes_left = {
            i: rows[i][0][jstar] != MISSING and rows[i][0][jstar] <= tstar for i in pool
        }
        left_count = sum(1 for i in pool if goes_left[i])
        right_count = len(pool) - left_count
        smaller = min(left_count, right_count)
        if smaller == 0:
            continue
        values = sorted({rows[i][0][k] for i in pool})
        if len(values) < 2:
            continue
        pick = None
        for u in values[:-1]:
            forward = sum(1 for i in pool if (rows[i][0][k] <= u) == goes_left[i])
            reverse = len(pool) - forward
            options = (
                [(forward, "F")]
                if variant == "fwdonly"
                else [(forward, "F"), (reverse, "V")]
            )
            for agree, direction in options:
                key = (-agree, u, 0 if direction == "F" else 1)
                if pick is None or key < pick[0]:
                    pick = (key, u, direction, agree)
        if pick is None:
            continue
        _key, u, direction, agree = pick
        association = Fraction(smaller - (len(pool) - agree), smaller)
        keep = association >= 0 if variant == "nonneg" else association > 0
        if keep:
            found.append((association, k, u, direction))
    found.sort(key=lambda e: (-e[0], e[1], e[2], 0 if e[3] == "F" else 1))
    return found


def route(features_row, node, variant):
    j, t = node["feature"], node["threshold"]
    if features_row[j] != MISSING:
        return "P", features_row[j] <= t
    for rank, (_a, k, u, direction) in enumerate(node["surrogates"], 1):
        if features_row[k] != MISSING:
            left = features_row[k] <= u if direction == "F" else features_row[k] > u
            return f"S{rank}", left
    if variant == "leftfall":
        return "B", True
    return "B", node["block_left"]


def build(
    rows, subset, features, classes, depth, max_depth, min_split, variant, counter
):
    node = {
        "id": counter[0],
        "depth": depth,
        "size": len(subset),
        "leaf": True,
        "label": majority(rows, subset, classes),
        "rows": list(subset),
    }
    counter[0] += 1
    labels = {rows[i][1] for i in subset}
    if depth >= max_depth or len(labels) <= 1 or len(subset) < min_split:
        return node
    chosen = best_split(rows, subset, features, classes)
    if chosen is None:
        return node
    jstar, tstar, gain = chosen
    node["leaf"] = False
    node["feature"] = jstar
    node["threshold"] = tstar
    node["gain"] = gain
    node["surrogates"] = surrogates(rows, subset, features, jstar, tstar, variant)
    observed = [i for i in subset if rows[i][0][jstar] != MISSING]
    left_count = sum(1 for i in observed if rows[i][0][jstar] <= tstar)
    node["block_left"] = left_count >= len(observed) - left_count
    left, right = [], []
    for i in subset:
        _via, goes_left = route(rows[i][0], node, variant)
        (left if goes_left else right).append(i)
    node["left"] = build(
        rows, left, features, classes, depth + 1, max_depth, min_split, variant, counter
    )
    node["right"] = build(
        rows,
        right,
        features,
        classes,
        depth + 1,
        max_depth,
        min_split,
        variant,
        counter,
    )
    return node


def collect(node, out):
    out.append(node)
    if not node["leaf"]:
        collect(node["left"], out)
        collect(node["right"], out)
    return out


def importances(root, features):
    primary = [Fraction(0)] * features
    substitute = [Fraction(0)] * features
    for node in collect(root, []):
        if node["leaf"]:
            continue
        primary[node["feature"]] += node["size"] * node["gain"]
        for association, k, _u, _d in node["surrogates"]:
            substitute[k] += node["size"] * association
    return primary, substitute


def descend(features_row, node, variant):
    evidence = Fraction(1)
    current = node
    while not current["leaf"]:
        via, goes_left = route(features_row, current, variant)
        if via == "B":
            evidence = Fraction(0)
        elif via != "P":
            rank = int(via[1:])
            evidence = min(evidence, current["surrogates"][rank - 1][0])
        current = current["left"] if goes_left else current["right"]
    return evidence, current


def posterior(rows, subset, classes):
    counts = [0] * classes
    for i in subset:
        counts[rows[i][1]] += 1
    total = len(subset)
    return [Fraction(c, total) for c in counts]


def parse_int(token):
    if not token.lstrip("+").isdigit():
        return None
    return int(token)


def _handle(tables, parts, variant):
    if len(parts) != 5:
        return None
    train_name, query_name = parts[1], parts[2]
    if train_name not in tables or query_name not in tables:
        return None
    max_depth = parse_int(parts[3])
    min_split = parse_int(parts[4])
    if max_depth is None or min_split is None:
        return None
    if max_depth < 1 or min_split < 2:
        return None
    rows = tables[train_name]
    probes = tables[query_name]
    if not rows or not probes:
        return None
    features = len(rows[0][0])
    if any(len(r[0]) != features for r in rows):
        return None
    if any(len(p[0]) != features for p in probes):
        return None
    classes = max(label for _f, label in rows) + 1
    counter = [0]
    root = build(
        rows,
        list(range(len(rows))),
        features,
        classes,
        0,
        max_depth,
        min_split,
        variant,
        counter,
    )
    qid = parts[0]
    lines = []
    primary, substitute = importances(root, features)
    for j in range(features):
        lines.append(
            f"{qid} V {j} "
            f"P {primary[j].numerator}/{primary[j].denominator} "
            f"S {substitute[j].numerator}/{substitute[j].denominator}"
        )
    for index, (features_row, _label) in enumerate(probes):
        evidence, leaf = descend(features_row, root, variant)
        impurity = gini(rows, leaf["rows"], classes)
        spread = posterior(rows, leaf["rows"], classes)
        shown = " ".join(f"{v.numerator}/{v.denominator}" for v in spread)
        lines.append(
            f"{qid} Q {index} C {leaf['label']} N {leaf['size']} "
            f"I {impurity.numerator}/{impurity.denominator} "
            f"E {evidence.numerator}/{evidence.denominator} D {shown}"
        )
    for node in collect(root, []):
        if node["leaf"]:
            continue
        lines.append(
            f"{qid} D {node['id']} V {node['feature']} T {node['threshold']} "
            f"N {node['size']} G {node['gain'].numerator}/{node['gain'].denominator}"
        )
    for node in collect(root, []):
        if node["leaf"]:
            continue
        for rank, (association, k, u, direction) in enumerate(node["surrogates"], 1):
            lines.append(
                f"{qid} G {node['id']} R {rank} V {k} T {u} D {direction} "
                f"A {association.numerator}/{association.denominator}"
            )
    return lines


def process(tables, lines, variant="pinned"):
    out = []
    for raw in lines:
        parts = raw.split()
        if not parts:
            continue
        result = _handle(tables, parts, variant)
        if result is None:
            out.append(f"{parts[0]} REJECT")
        else:
            out.extend(result)
    return out
