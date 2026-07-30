Scopes are resource-qualified and matched exactly unless wildcard rules apply at the event-time policy revision.

A `scope_decision` event may express the required scope as `payload.required_scope`, `payload.required.resource_scope`, or `payload.scope.required`. Granted scopes may appear as `payload.granted_scopes`, `payload.granted.scopes`, or `payload.scopes.granted`. Implementations must normalize these shapes before comparison.

When `payload.decision` is present, only `allow` or `granted` decisions may produce `scope_escalation`. A `deny` decision with the same nested shape must not escalate even if the granted scope list contains the required scope.

A scope escalation finding is produced only when all of these are true:

- the decision is allowed/granted;
- the required resource-qualified scope is present in the normalized granted scope set by exact match or by a wildcard rule active at the event's policy revision;
- the resource tenant or audience is outside the requesting tenant's allowed boundary;
- the event is not a denial or blocked candidate.

A bare prefix match such as `startswith(required, granted)` is not sufficient. `read:tenant-a` must not imply `read:tenant-a-extra`, and `read:*` only applies when the active policy revision declares that wildcard.
