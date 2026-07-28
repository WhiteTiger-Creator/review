# Site storage operations

`/app/usr/sbin/site-admin` is used while a target is detached from normal consumers. It accepts one state-directory argument. Each target contains a `payload` tree owned by the tenant and a `.site` directory owned by administration.

Boot entry uses `/app/usr/sbin/site-activate` with the same target argument. Both entrypoints are expected to leave recoverable targets in a state accepted by `/app/bin/site-core check`. A nonzero return keeps the target out of service. Targets marked busy belong to a running consumer and are not eligible for offline work.

`/app/bin/site-core` is the sealed installed utility for local volume probes, transitions, and operator summaries. Operators drive offline recovery through the administration and activation entrypoints rather than by replacing that binary. `/app/bin/site-core inspect TARGET` prints a read-only summary for operator logs with lines such as `root=valid`, `busy=no`, `pending=no`, `account=current`, and `state=serviceable` on a healthy target. `/app/bin/site-core check TARGET` prints the same summary and exits zero only for a serviceable target. The utility also exposes inventory and marker helpers used by other local tooling.

Administrative accounting is kept durable across abrupt interruption. Among durable candidates that match the live payload, the newer generation is authoritative. Sequence values are transaction identifiers, not wall-clock timestamps. Deferred records under `.site/pending` may retire namespace entries or request administrative acknowledgements. The local event ledger records finished acknowledgements as `kept=` lines (for example `kept=audit/trail`) and may also contain `noted=retired/link` or `noted=retired/second` lines produced while processing deferred drop records. Accounting fingerprints cover the live payload path set together with each file's bytes. An observed inventory under `.site/observed` supports local comparison against durable accounting.

The lab creator under `tools` can prepare representative targets for maintenance rehearsals. The extended rehearsal layout includes a second retired entry at `namespace/retired/second`.
