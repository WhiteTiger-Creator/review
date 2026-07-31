import random
import sys

NS = "http://ex.org/k8s#"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
XSD_BOOL = "http://www.w3.org/2001/XMLSchema#boolean"

ZONES = ["zone_a", "zone_b", "zone_c", "zone_d"]
RACKS = ["rack_1", "rack_2", "rack_3", "rack_4", "rack_5", "rack_6", "rack_7", "rack_8"]

# Structural sizes are fixed so every seed yields identical node/pod counts;
# only identities and the generic assignments vary with the seed.
NODE_TOTAL = 40
PENDING_TOTAL = 30
PLACED_TOTAL = 120
RESERVED_NODES = 13
RESERVED_PENDING = 16
RESERVED_PLACED = 8
GENERIC_FRONTEND_CARRIERS = 6
GENERIC_REPLICA_CARRIERS = 5


def build(seed):
    rng = random.Random(seed)
    used = set()

    def newid(prefix):
        while True:
            ident = prefix + "".join(rng.choice("0123456789abcdef") for _ in range(8))
            if ident not in used:
                used.add(ident)
                return ident

    label_map = {}
    label_defs = []

    def label(key, value):
        if (key, value) not in label_map:
            iri = NS + newid("label_")
            label_map[(key, value)] = iri
            label_defs.append((iri, key, value))
        return label_map[(key, value)]

    taint_defs = []

    def taint(key, value, effect):
        iri = NS + newid("taint_")
        taint_defs.append((iri, key, value, effect))
        return iri

    tol_defs = []

    def toleration(key, operator, value, effect):
        iri = NS + newid("tol_")
        tol_defs.append((iri, key, operator, value, effect))
        return iri

    aa_defs = []

    def antiaffinity(selector, topology_key):
        iri = NS + newid("aa_")
        aa_defs.append((iri, selector, topology_key))
        return iri

    nodes = {}

    def node(zone, rack, disk, tier, taint_list):
        iri = NS + newid("node_")
        labs = [label("zone", zone)]
        if rack is not None:
            labs.append(label("rack", rack))
        if disk is not None:
            labs.append(label("disk", disk))
        if tier is not None:
            labs.append(label("tier", tier))
        nodes[iri] = {"labels": labs, "taints": list(taint_list)}
        return iri

    pods = {}

    def pod(pending, placed_on, pod_labels, tols, requires, aa):
        iri = NS + newid("pod_")
        pods[iri] = {
            "pending": pending,
            "placedOn": placed_on,
            "podLabels": list(pod_labels),
            "tols": list(tols),
            "requires": list(requires),
            "aa": aa,
        }
        return iri

    # Reserved nodes carry the pinned topology, taint and label shapes every
    # obligation-liveness probe and anchor depends on, so they are never left
    # to the generic draw below.
    n_clean_1 = node("zone_a", "rack_1", "ssd", "gold", [])
    n_clean_2 = node("zone_a", "rack_2", "ssd", "silver", [])
    n_evict_free = node("zone_a", "rack_2", "hdd", "silver", [])
    n_maint = node(
        "zone_a",
        "rack_1",
        "ssd",
        "silver",
        [
            taint("spot", "true", "NoSchedule"),
            taint("maintenance", "planned", "NoExecute"),
        ],
    )
    n_ded_infra = node(
        "zone_b", "rack_3", "ssd", "silver", [taint("dedicated", "infra", "NoSchedule")]
    )
    n_ded_ml = node(
        "zone_b", "rack_4", "ssd", "silver", [taint("dedicated", "ml", "NoSchedule")]
    )
    n_conflict_host = node("zone_b", "rack_8", "hdd", "silver", [])
    n_zoneb_peer = node("zone_b", "rack_3", "hdd", "silver", [])
    n_two_taint = node(
        "zone_c",
        "rack_5",
        "ssd",
        "silver",
        [
            taint("dedicated", "ml", "NoSchedule"),
            taint("gpu", "true", "NoSchedule"),
        ],
    )
    n_prefer = node(
        "zone_c", "rack_6", "hdd", "silver", [taint("spot", "true", "PreferNoSchedule")]
    )
    n_nosched_stuck = node(
        "zone_c", "rack_7", "hdd", "silver", [taint("dedicated", "infra", "NoSchedule")]
    )
    n_norack_1 = node("zone_d", None, "ssd", "silver", [])
    n_norack_2 = node("zone_d", None, "hdd", "silver", [])

    for i in range(NODE_TOTAL - RESERVED_NODES):
        zone = ZONES[i % len(ZONES)]
        rack = RACKS[i % len(RACKS)] if rng.random() < 0.8 else None
        disk = rng.choice(["ssd", "hdd"])
        tier = rng.choice(["gold", "silver"])
        extra = []
        roll = rng.random()
        if roll < 0.15:
            extra.append(taint("spot", "true", "PreferNoSchedule"))
        elif roll < 0.30:
            extra.append(taint("dedicated", rng.choice(["infra", "ml"]), "NoSchedule"))
        elif roll < 0.40:
            extra.append(taint("maintenance", "planned", "NoExecute"))
        node(zone, rack, disk, tier, extra)

    # Reserved selector labels stay out of the generic pod-label draw so the
    # anti-affinity domains the anchors reason about are fully pinned.
    l_cache = label("app", "cache")
    l_api = label("app", "api")
    l_web = label("app", "web")
    l_batch = label("app", "batch")
    l_primary = label("role", "primary")
    l_frontend = label("app", "frontend")
    l_replica = label("role", "replica")

    pl_cache_resident = pod(False, n_clean_1, [l_cache], [], [], None)
    pl_api_resident = pod(False, n_conflict_host, [l_api], [], [], None)
    pl_web_resident = pod(False, n_conflict_host, [l_web], [], [], None)
    pl_batch_resident = pod(False, n_conflict_host, [l_batch], [], [], None)
    # Tolerates the spot NoSchedule taint on its host but not the maintenance
    # NoExecute one, so it is evicted and stops occupying zone_a. An
    # existential reading of tolerance keeps it resident instead.
    pl_partial_evicted = pod(
        False,
        n_maint,
        [l_batch],
        [toleration("spot", "Equal", "true", "NoSchedule")],
        [],
        None,
    )
    # Fails a NoSchedule taint on its host, which does not evict, so it stays
    # resident and keeps occupying zone_c.
    pl_noschedule_stuck = pod(False, n_nosched_stuck, [l_primary], [], [], None)
    pl_wildcard_resident = pod(
        False, n_maint, [l_cache], [toleration("", "Exists", "", "")], [], None
    )
    # Its toleration names the right taint key but the wrong effect, so the
    # NoExecute taint is untolerated and it is evicted.
    pl_empty_effect_evicted = pod(
        False,
        n_maint,
        [l_web],
        [toleration("maintenance", "Equal", "planned", "NoSchedule")],
        [],
        None,
    )

    p_exists_vs_equal = pod(
        True,
        None,
        [],
        [toleration("dedicated", "Equal", "infra", "NoSchedule")],
        [],
        None,
    )
    p_equal_wrong_value = pod(
        True, None, [], [toleration("dedicated", "Equal", "ml", "NoSchedule")], [], None
    )
    p_exists_any_value = pod(
        True, None, [], [toleration("dedicated", "Exists", "", "NoSchedule")], [], None
    )
    p_empty_effect = pod(
        True,
        None,
        [],
        [
            toleration("maintenance", "Equal", "planned", ""),
            toleration("spot", "Equal", "true", ""),
        ],
        [],
        None,
    )
    p_empty_key_wildcard = pod(
        True, None, [], [toleration("", "Exists", "", "")], [], None
    )
    p_prefer_only = pod(True, None, [], [], [], None)
    p_two_taint_partial = pod(
        True, None, [], [toleration("dedicated", "Equal", "ml", "NoSchedule")], [], None
    )
    p_missing_topokey = pod(True, None, [], [], [], antiaffinity(l_cache, "rack"))
    p_cross_node_domain = pod(True, None, [], [], [], antiaffinity(l_api, "zone"))
    p_selector_miss = pod(
        True, None, [], [], [label("disk", "ssd"), label("tier", "gold")], None
    )
    p_count_zero = pod(True, None, [], [], [label("tier", "platinum")], None)
    p_wildcard_conflict = pod(
        True,
        None,
        [],
        [toleration("", "Exists", "", "")],
        [],
        antiaffinity(l_batch, "zone"),
    )
    p_evict_rescue = pod(True, None, [], [], [], antiaffinity(l_batch, "zone"))
    p_noexec_asym = pod(True, None, [], [], [], antiaffinity(l_primary, "zone"))
    p_resident_conflict = pod(True, None, [], [], [], antiaffinity(l_web, "rack"))
    p_both_signs = pod(
        True,
        None,
        [],
        [toleration("dedicated", "Equal", "ml", "NoSchedule")],
        [],
        antiaffinity(l_batch, "zone"),
    )

    for _ in range(PENDING_TOTAL - RESERVED_PENDING):
        tols = []
        if rng.random() < 0.5:
            tols.append(
                toleration(
                    "dedicated",
                    rng.choice(["Equal", "Exists"]),
                    rng.choice(["infra", "ml"]),
                    rng.choice(["NoSchedule", ""]),
                )
            )
        if rng.random() < 0.35:
            tols.append(
                toleration(
                    "maintenance", "Equal", "planned", rng.choice(["NoExecute", ""])
                )
            )
        requires = []
        if rng.random() < 0.3:
            requires.append(label("disk", rng.choice(["ssd", "hdd"])))
        if rng.random() < 0.2:
            requires.append(label("tier", rng.choice(["gold", "silver"])))
        aa = None
        if rng.random() < 0.5:
            aa = antiaffinity(
                rng.choice([l_frontend, l_replica]),
                "rack" if rng.random() < 0.75 else "zone",
            )
        pod(True, None, [], tols, requires, aa)

    # The generic selector labels stay deliberately scarce: a selector carried
    # by many placed pods would occupy every topology domain at once and drive
    # every anti-affinity count to zero, collapsing the contrast the audit
    # turns on.
    host_pool = list(nodes)
    generic_placed = []
    for _ in range(PLACED_TOTAL - RESERVED_PLACED):
        tols = []
        if rng.random() < 0.5:
            tols.append(
                toleration(
                    "maintenance", "Equal", "planned", rng.choice(["NoExecute", ""])
                )
            )
        if rng.random() < 0.4:
            tols.append(toleration("spot", "Exists", "", "NoSchedule"))
        generic_placed.append(pod(False, rng.choice(host_pool), [], tols, [], None))

    for carrier in rng.sample(generic_placed, GENERIC_FRONTEND_CARRIERS):
        pods[carrier]["podLabels"].append(l_frontend)
    for carrier in rng.sample(generic_placed, GENERIC_REPLICA_CARRIERS):
        pods[carrier]["podLabels"].append(l_replica)

    triples = []

    def iri(s, p, o):
        triples.append((s, p, ("iri", o)))

    def lit(s, p, o):
        triples.append((s, p, ("lit", o)))

    for ident, key, value in label_defs:
        iri(ident, RDF_TYPE, NS + "Label")
        lit(ident, NS + "key", key)
        lit(ident, NS + "value", value)
    for ident, key, value, effect in taint_defs:
        iri(ident, RDF_TYPE, NS + "Taint")
        lit(ident, NS + "key", key)
        lit(ident, NS + "value", value)
        lit(ident, NS + "effect", effect)
    for ident, key, operator, value, effect in tol_defs:
        iri(ident, RDF_TYPE, NS + "Toleration")
        lit(ident, NS + "key", key)
        lit(ident, NS + "operator", operator)
        lit(ident, NS + "value", value)
        lit(ident, NS + "effect", effect)
    for ident, selector, topology_key in aa_defs:
        iri(ident, RDF_TYPE, NS + "AntiAffinity")
        iri(ident, NS + "selectorLabel", selector)
        lit(ident, NS + "topologyKey", topology_key)
    for ident, data in nodes.items():
        iri(ident, RDF_TYPE, NS + "Node")
        for lab in data["labels"]:
            iri(ident, NS + "hasLabel", lab)
        for tnt in data["taints"]:
            iri(ident, NS + "hasTaint", tnt)
    for ident, data in pods.items():
        iri(ident, RDF_TYPE, NS + "Pod")
        triples.append(
            (ident, NS + "pending", ("bool", "true" if data["pending"] else "false"))
        )
        if data["placedOn"] is not None:
            iri(ident, NS + "placedOn", data["placedOn"])
        for lab in data["podLabels"]:
            iri(ident, NS + "hasPodLabel", lab)
        for tol in data["tols"]:
            iri(ident, NS + "hasToleration", tol)
        for lab in data["requires"]:
            iri(ident, NS + "requiresLabel", lab)
        if data["aa"] is not None:
            iri(ident, NS + "hasAntiAffinity", data["aa"])

    rng.shuffle(triples)

    return {
        "triples": triples,
        "nodes": nodes,
        "pods": pods,
        "labels": label_map,
        "reserved_nodes": {
            "clean_1": n_clean_1,
            "clean_2": n_clean_2,
            "evict_free": n_evict_free,
            "maint": n_maint,
            "ded_infra": n_ded_infra,
            "ded_ml": n_ded_ml,
            "conflict_host": n_conflict_host,
            "zoneb_peer": n_zoneb_peer,
            "two_taint": n_two_taint,
            "prefer": n_prefer,
            "nosched_stuck": n_nosched_stuck,
            "norack_1": n_norack_1,
            "norack_2": n_norack_2,
        },
        "reserved_pending": {
            "exists_vs_equal": p_exists_vs_equal,
            "equal_wrong_value": p_equal_wrong_value,
            "exists_any_value": p_exists_any_value,
            "empty_effect": p_empty_effect,
            "empty_key_wildcard": p_empty_key_wildcard,
            "prefer_only": p_prefer_only,
            "two_taint_partial": p_two_taint_partial,
            "missing_topokey": p_missing_topokey,
            "cross_node_domain": p_cross_node_domain,
            "selector_miss": p_selector_miss,
            "count_zero": p_count_zero,
            "wildcard_conflict": p_wildcard_conflict,
            "evict_rescue": p_evict_rescue,
            "noexec_asym": p_noexec_asym,
            "resident_conflict": p_resident_conflict,
            "both_signs": p_both_signs,
        },
        "reserved_placed": {
            "cache_resident": pl_cache_resident,
            "api_resident": pl_api_resident,
            "web_resident": pl_web_resident,
            "batch_resident": pl_batch_resident,
            "partial_evicted": pl_partial_evicted,
            "noschedule_stuck": pl_noschedule_stuck,
            "wildcard_resident": pl_wildcard_resident,
            "empty_effect_evicted": pl_empty_effect_evicted,
        },
    }


def to_nt(triples):
    out = []
    for s, p, obj in triples:
        kind, value = obj
        if kind == "iri":
            term = f"<{value}>"
        elif kind == "bool":
            term = f'"{value}"^^<{XSD_BOOL}>'
        else:
            term = f'"{value}"'
        out.append(f"<{s}> <{p}> {term} .\n")
    return "".join(out)


def main(argv):
    seed = argv[1]
    out = argv[2]
    model = build(seed)
    with open(out, "w") as fh:
        fh.write(to_nt(model["triples"]))


if __name__ == "__main__":
    main(sys.argv)
