package tokenexposure.grant

import rego.v1

payload_or_empty(ev) := p if {
	p := ev.payload
	p != null
} else := {}

required_scope(payload) := scope if {
	scope := object.get(payload, "required_scope", "")
	scope != ""
}

required_scope(payload) := scope if {
	required := object.get(payload, "required", {})
	scope := object.get(required, "resource_scope", "")
	scope != ""
}

required_scope(payload) := scope if {
	scope_obj := object.get(payload, "scope", {})
	scope := object.get(scope_obj, "required", "")
	scope != ""
}

granted_scope_set(payload) := scopes if {
	scopes := object.get(payload, "granted_scopes", [])
	is_array(scopes)
	count(scopes) > 0
}

granted_scope_set(payload) := scopes if {
	granted := object.get(payload, "granted", {})
	scopes := object.get(granted, "scopes", [])
	is_array(scopes)
	count(scopes) > 0
}

granted_scope_set(payload) := scopes if {
	scope_obj := object.get(payload, "scope", {})
	scopes := object.get(scope_obj, "granted", [])
	is_array(scopes)
	count(scopes) > 0
}

decision_allowed(payload) if {
	object.get(payload, "decision", "allow") in {"allow", "granted"}
}

escalation_findings(events) := [f |
	some i
	ev := events[i]
	ev.event_type == "scope_decision"
	payload := payload_or_empty(ev)
	decision_allowed(payload)
	required := required_scope(payload)
	granted := granted_scope_set(payload)[_]
	granted == required
	resource_tenant := object.get(payload, "resource_tenant", ev.tenant_id)
	ev.tenant_id != resource_tenant
	f := {
		"class": "scope_escalation",
		"tenant_id": ev.tenant_id,
		"evidence_event_ids": [ev.event_id],
	}
]
