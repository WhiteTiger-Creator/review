package tokenexposure.graph

nodes(events, findings) := sort(node_list(events, findings), less_node)

node_list(events, findings) := [n |
    some i
    f := findings[i]
    n := {"node_id": node_id("finding", f.class), "label": f.class, "class": "finding", "tenant_id": f.tenant_id}
]

edges(events, findings) := [e |
    some i
    f := findings[i]
    e := {"edge_id": edge_id(f), "source": node_id("finding", f.class), "target": node_id("tenant", f.tenant_id), "label": "exposure", "class": "used_at"}
]

node_id(kind, material) := sprintf("%s_%s", [kind, substr(sprintf("%x", [material]), 0, 10)])

edge_id(f) := sprintf("edge_%s", [substr(sprintf("%x", [f.class]), 0, 10)])

less_node(a, b) if a.node_id < b.node_id
