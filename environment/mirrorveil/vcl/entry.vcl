vcl 4.1;

import std;
import directors;

include "/srv/mirrorveil/vcl/backend-pool.vcl";
include "/srv/mirrorveil/vcl/request-boundary.vcl";
include "/srv/mirrorveil/vcl/object-policy.vcl";
include "/srv/mirrorveil/vcl/delivery-state.vcl";
include "/srv/mirrorveil/vcl/invalidation.vcl";

acl mirror_loopback {
    "127.0.0.1";
    "::1";
}

sub vcl_init {
    call mirror_backend_init;
}

sub vcl_recv {
    call mirror_invalidate_recv;
    set req.backend_hint = mirror_pool.backend();
    call mirror_request_boundary_recv;
}

sub vcl_hash {
    hash_data(req.url);
    if (req.http.Host) {
        hash_data(req.http.Host);
    }
}

sub vcl_backend_response {
    call mirror_object_policy_beresp;
}

sub vcl_deliver {
    call mirror_delivery_state_deliver;
}

sub vcl_synth {
    call mirror_delivery_state_synth;
}
