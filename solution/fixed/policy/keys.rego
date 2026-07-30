package tokenexposure.keys

signing_key_reuse(events) := findings if {
    findings := [f |
        some i, j
        i < j
        a := events[i]
        b := events[j]
        a.event_type == "token_issued"
        b.event_type == "token_issued"
        same_material(a, b)
        a.payload.issuer != b.payload.issuer
        f := {
            "class": "signing_key_reuse",
            "tenant_id": a.tenant_id,
            "evidence_event_ids": [a.event_id, b.event_id]
        }
    ]
}

same_material(a, b) if {
    a.payload.material_id == b.payload.material_id
    a.payload.material_id != ""
}

key_match(k, issuer, kid) if k.issuer == issuer; k.kid == kid
