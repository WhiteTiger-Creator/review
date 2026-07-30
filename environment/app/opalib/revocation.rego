package tokenexposure.revocation

import rego.v1

lag_findings(events) := [f |
	some i, j
	rev := events[i]
	use := events[j]
	rev.event_type == "token_revoked"
	use.event_type == "token_used"
	rev.payload.token_fingerprint == use.payload.token_fingerprint
	use.observed_at > rev.observed_at
	use.observed_at < rev.payload.effective_at
	f := {
		"class": "revocation_lag_exposure",
		"tenant_id": use.tenant_id,
		"evidence_event_ids": [rev.event_id, use.event_id],
	}
]

replay_findings(events) := [f |
	some i
	ev := events[i]
	ev.event_type == "refresh_used"
	ev.payload.replay == true
	f := {
		"class": "refresh_token_replay",
		"tenant_id": ev.tenant_id,
		"evidence_event_ids": [ev.event_id],
	}
]
