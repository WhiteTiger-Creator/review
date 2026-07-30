package tokenexposure.hop

import rego.v1

payload_or_empty(ev) := p if {
	p := ev.payload
	p != null
} else := {}

proxy_id(ev) := object.get(payload_or_empty(ev), "proxy_id", "")

untrusted_proxy(pid) if {
	some i
	input.trust_boundaries.untrusted_proxies[i] == pid
}

bearer_findings(events) := [f |
	some i
	ev := events[i]
	ev.event_type == "token_forwarded"
	pid := proxy_id(ev)
	pid != ""
	pid != null
	untrusted_proxy(pid)
	f := {
		"class": "bearer_forwarding",
		"tenant_id": ev.tenant_id,
		"evidence_event_ids": [ev.event_id],
	}
]

rejected_forward(events) := [r |
	some i
	ev := events[i]
	ev.event_type in {"egress_blocked", "token_forward_attempted"}
	r := {
		"reason": "blocked_forward",
		"event_id": ev.event_id,
	}
]

rejected_blocked(events) := rejected_forward(events)
