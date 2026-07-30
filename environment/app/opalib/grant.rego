package tokenexposure.grant

import rego.v1

escalation_findings(events) := [f |
	some i
	ev := events[i]
	ev.event_type == "scope_decision"
	granted := ev.payload.granted_scopes[_]
	required := ev.payload.required_scope
	scope_implies(granted, required)
	not tenant_allowed(ev, required)
	f := {
		"class": "scope_escalation",
		"tenant_id": ev.tenant_id,
		"evidence_event_ids": [ev.event_id],
	}
]

scope_implies(granted, required) if {
	startswith(required, granted)
}

tenant_allowed(ev, scope) if {
	ev.tenant_id == ev.payload.resource_tenant
}
