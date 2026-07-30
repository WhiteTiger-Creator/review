package tokenexposure.findings

import rego.v1

import data.tokenexposure.keys
import data.tokenexposure.hop
import data.tokenexposure.grant
import data.tokenexposure.revocation
import data.tokenexposure.graph
import data.tokenexposure.compat

evaluate(events, chains, ctx) := {
	"findings": canonical_findings(events),
	"rejected_candidates": hop.rejected_blocked(events),
	"nodes": graph.nodes(events, canonical_findings(events)),
	"edges": graph.edges(events, canonical_findings(events)),
	"legacy_compatibility": compat.legacy(events),
}

canonical_findings(events) := sort(findings_list(events))

findings_list(events) := array.concat(
	array.concat(
		array.concat(keys.signing_key_reuse(events), hop.bearer_findings(events)),
		grant.escalation_findings(events),
	),
	array.concat(revocation.lag_findings(events), revocation.replay_findings(events)),
)
