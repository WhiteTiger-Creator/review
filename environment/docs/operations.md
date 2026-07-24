# Site storage operations

`/app/usr/sbin/site-admin` is used while a target is detached from normal consumers. It accepts one state-directory argument. Each target contains a `payload` tree owned by the tenant and a `.site` directory owned by administration.

Boot entry uses `/app/usr/sbin/site-activate` with the same target argument. Both entrypoints are expected to leave recoverable targets in a state accepted by `/app/bin/site-core check`. A nonzero return keeps the target out of service. Targets marked busy belong to a running consumer and are not eligible for offline work.

`/app/bin/site-core inspect TARGET` prints a read-only summary for operator logs with lines such as `root=valid`, `busy=no`, `pending=no`, `account=current`, and `state=serviceable` on a healthy target. `/app/bin/site-core check TARGET` prints the same summary and exits zero only for a serviceable target. Lower-level `commit` and `publish` actions refuse while deferred namespace work remains.

The installation keeps two durable accounting slots because power loss can interrupt replacement of an accounting record. Among slots that match the live payload, the newer generation is authoritative. Sequence values are transaction identifiers, not wall-clock timestamps. Namespace actions are recorded separately from payload content so payload files are never deleted by administrative replay. Accounting fingerprints cover payload path names and file bytes together: for each live file, the relative path bytes are followed immediately by that file's contents, with no separator between them.

The lab creator under `tools` can prepare representative targets for maintenance rehearsals. The extended rehearsal layout includes a second retired entry at `namespace/retired/second`.
