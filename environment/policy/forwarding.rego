package tokenexposure.forwarding

bearer_findings(events) := [f |
    some i
    ev := events[i]
    forward_exposure(ev) if ev.event_type in {"token_forwarded", "token_forward_attempted", "egress_blocked"}
    f := {
        "class": "bearer_forwarding",
        "tenant_id": ev.tenant_id,
        "evidence_event_ids": [ev.event_id]
    }
]

rejected_blocked(events) := [r |
    some i
    ev := events[i]
    ev.event_type == "egress_blocked"
    r := {
        "reason": "blocked_forward",
        "event_id": ev.event_id
    }
]
