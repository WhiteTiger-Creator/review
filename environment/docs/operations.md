# Local site storage operations

The manual `/app/usr/sbin/site-admin` entrypoint is used while a target is detached from normal consumers. It accepts one state-directory argument. Each target contains a `payload` tree owned by the tenant and a `.site` directory owned by local administration.

Activation uses `/app/usr/sbin/site-activate` with the same target argument. Both entrypoints are expected to leave recoverable targets in a state accepted by `site-core check`. A nonzero return keeps the target out of service. Targets marked busy belong to a running consumer and are not eligible for offline work.

The installation keeps two durable candidate slots because power loss can interrupt replacement of an accounting record. Sequence values are local transaction identifiers, not wall-clock timestamps. Namespace actions are recorded separately from payload content so payload files are never deleted by administrative replay.

`/app/bin/site-core inspect TARGET` provides a read-only summary suitable for operator logs. The lab creator under `tools` can prepare representative targets for maintenance rehearsals.

The extended rehearsal layout includes a second retired entry at `namespace/retired/second`.
