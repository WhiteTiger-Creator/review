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

payload_or_empty(ev) := p if {
	p := ev.payload
	p != null
} else := {}

chain_key(ev) := sprintf("%s|%s", [ev.tenant_id, exchange]) if {
	payload := payload_or_empty(ev)
	exchange := object.get(payload, "exchange_id", "")
	exchange != ""
}

chain_key(ev) := sprintf("%s|%s", [ev.tenant_id, trace]) if {
	payload := payload_or_empty(ev)
	not object.get(payload, "exchange_id", "")
	trace := object.get(ev, "trace_id", "")
	trace != ""
	trace != null
}

chain_key(ev) := sprintf("%s|%s", [ev.tenant_id, family]) if {
	payload := payload_or_empty(ev)
	not object.get(payload, "exchange_id", "")
	not object.get(ev, "trace_id", "")
	family := object.get(payload, "refresh_family", "")
	family != ""
}

chain_key(ev) := sprintf("%s|%s", [ev.tenant_id, family]) if {
	payload := payload_or_empty(ev)
	not object.get(payload, "exchange_id", "")
	not object.get(ev, "trace_id", "")
	not object.get(payload, "refresh_family", "")
	family := object.get(payload, "refresh_family_id", "")
	family != ""
}

chain_key(ev) := sprintf("%s|%s", [ev.tenant_id, req]) if {
	payload := payload_or_empty(ev)
	not object.get(payload, "exchange_id", "")
	not object.get(ev, "trace_id", "")
	not object.get(payload, "refresh_family", "")
	not object.get(payload, "refresh_family_id", "")
	req := object.get(ev, "request_id", "")
}
