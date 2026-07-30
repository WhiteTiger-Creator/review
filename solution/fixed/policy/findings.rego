package tokenexposure.findings

import data.tokenexposure.keys
import data.tokenexposure.forwarding
import data.tokenexposure.scopes
import data.tokenexposure.revocation
import data.tokenexposure.graph
import data.tokenexposure.compat

evaluate(events, chains, input) := {
    "findings": canonical_findings(events),
    "rejected_candidates": forwarding.rejected_blocked(events),
    "nodes": graph.nodes(events, canonical_findings(events)),
    "edges": graph.edges(events, canonical_findings(events)),
    "legacy_compatibility": compat.legacy(events)
}

canonical_findings(events) := sort(findings_list(events), less_finding)

findings_list(events) := array.concat(
    array.concat(
        array.concat(keys.signing_key_reuse(events), forwarding.bearer_findings(events)),
        scopes.escalation_findings(events)
    ),
    array.concat(revocation.lag_findings(events), revocation.replay_findings(events))
)

less_finding(a, b) if a.class < b.class
