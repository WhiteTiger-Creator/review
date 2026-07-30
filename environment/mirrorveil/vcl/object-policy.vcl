# Starter object policy: do not retain shared objects.

sub mirror_object_policy_beresp {
    set beresp.uncacheable = true;
    set beresp.ttl = 0s;
    set beresp.grace = 0s;
    set beresp.keep = 0s;
    return (deliver);
}
