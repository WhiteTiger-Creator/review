package tokenexposure.graph

import rego.v1

nodes(events, findings) := sort(node_list(events, findings))

node_list(events, findings) := [n |
	some i
	f := findings[i]
	n := {
		"node_id": node_id("finding", f.class),
		"label": f.class,
		"class": "finding",
		"tenant_id": f.tenant_id,
	}
]

edges(events, findings) := sort([e |
	some i
	f := findings[i]
	e := {
		"edge_id": edge_id(f),
		"source": node_id("finding", f.class),
		"target": node_id("tenant", f.tenant_id),
		"label": "exposure",
		"class": "used_at",
	}
])

node_id(kind, material) := sprintf("%s_%s", [kind, graph_safe(substring(sprintf("%v", [material]), 0, 32))])

edge_id(f) := sprintf("edge_%s", [graph_safe(substring(sprintf("%v", [f.class]), 0, 32))])

graph_safe(s) := regex.replace(s, `[^A-Za-z0-9_]`, "_")
