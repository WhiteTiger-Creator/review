# Starter delivery markers: emit a fixed pass label for client visibility.

sub mirror_delivery_state_deliver {
    set resp.http.X-Edge-State = "PASS";
}

sub mirror_delivery_state_synth {
    set resp.http.X-Edge-State = "SYNTH";
}
