Only successful `token_forwarded` events that cross from a trusted actor to an untrusted proxy constitute `bearer_forwarding`.

The untrusted proxy set comes from `/app/config/trust-boundaries.json`. A forwarding event is an exposure when `payload.proxy_id` is in that set and the event outcome is successful. Supported success shapes include either `event_type == "token_forwarded"` or a payload/status field that explicitly records success for the forwarding operation.

`token_forward_attempted`, `egress_blocked`, denied forwarding decisions, and events whose proxy is not untrusted are rejected candidates rather than exposure findings. Rejected candidates must include the source `event_id` and a stable reason such as `blocked_forward`.

The policy must tolerate missing optional payload fields. A missing proxy id is not an exposure and must not cause an OPA evaluation error.
