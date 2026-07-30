package tokenexposure.normalize

import rego.v1

sorted_events(events) := sort([e | some i; e := enrich(events[i])])

enrich(ev) := result if {
	result := object.union(ev, {"logical_ts": logical_ts(ev)})
}

logical_ts(ev) := ts if {
	ts := ev.observed_at
}

collector_offset(_) := 0
