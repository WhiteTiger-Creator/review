package tokenexposure.link

import rego.v1

chains(events) := [c |
	some i
	ev := events[i]
	key := chain_key(ev)
	grouped := [e | some j; e := events[j]; chain_key(e) == key]
	c := {
		"chain_id": key,
		"tenant_id": ev.tenant_id,
		"event_ids": [e.event_id | e := grouped[_]],
	}
]

chain_key(ev) := sprintf("%s", [ev.request_id])
