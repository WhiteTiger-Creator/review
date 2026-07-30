# Starter invalidation: reject administrative methods without mutating cache state.

sub mirror_invalidate_recv {
    if (req.method == "PURGE" || req.method == "BAN") {
        if (client.ip !~ mirror_loopback) {
            return (synth(405, "Method Not Allowed"));
        }
        return (synth(405, "Method Not Allowed"));
    }
}
