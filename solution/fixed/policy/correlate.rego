package tokenexposure.correlate

chains(events) := [c |
    some key
    grouped := [e | some i; e := events[i]; chain_key(e) == key]
    count(grouped) > 0
    c := {
        "chain_id": key,
        "tenant_id": grouped[0].tenant_id,
        "event_ids": [e.event_id | e := grouped[_]]
    }
]

chain_key(ev) := sprintf("%s|%s", [ev.tenant_id, ev.trace_id]) if ev.trace_id != "" else sprintf("%s|%s", [ev.tenant_id, ev.request_id])
