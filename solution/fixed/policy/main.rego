package tokenexposure

import data.tokenexposure.normalize
import data.tokenexposure.correlate
import data.tokenexposure.keys
import data.tokenexposure.forwarding
import data.tokenexposure.scopes
import data.tokenexposure.revocation
import data.tokenexposure.findings
import data.tokenexposure.graph
import data.tokenexposure.redact
import data.tokenexposure.compat

default analysis := {
    "findings": [],
    "rejected_candidates": [],
    "nodes": [],
    "edges": [],
    "legacy_compatibility": {}
}

analysis := result if {
    events := normalize.sorted_events(input.events)
    chains := correlate.chains(events)
    result := findings.evaluate(events, chains, input)
}
