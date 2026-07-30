package tokenexposure

import rego.v1

import data.tokenexposure.normalize
import data.tokenexposure.link
import data.tokenexposure.findings

default analysis := {
	"findings": [],
	"rejected_candidates": [],
	"nodes": [],
	"edges": [],
	"legacy_compatibility": {},
}

analysis := result if {
	events := normalize.sorted_events(input.events)
	chains := link.chains(events)
	result := findings.evaluate(events, chains, input)
}
