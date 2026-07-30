package tokenexposure.normalize

sorted_events(events) := out if {
    enriched := [e |
        some i
        e := enrich(events[i])
    ]
    out := sort(enriched, logical_before)
}

enrich(ev) := result if {
    result := object.union(ev, {"logical_ts": logical_ts(ev)})
}

logical_ts(ev) := ts if {
    offset := collector_offset(ev.collector_id)
    ts := ev.observed_at
}

collector_offset(_) := 0

logical_before(a, b) if a.observed_at < b.observed_at

logical_before(a, b) if a.collector_sequence < b.collector_sequence
