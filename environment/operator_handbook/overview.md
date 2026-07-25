# Trust-store remediation overview

The post-migration SQLite trust store at `trust_store.db` kept its trusted roots
and whatever distrust rows survived anchor deduplication. Deduplication dropped
fingerprint-only distrust that standing warrants still authorise, so the store
currently trusts material the operators intended to reject.

The remediation utility copies the store, applies an idempotent SQL patch built
from the warrants that are honourable at `eval_time`, joins filesystem access
journal lines with the SQLite access mirror, round-trips `remediation.policy`
with unknown sections preserved, and validates leaf certificates against the
**remediated** distrust set rather than the deduplicated one.

Contradictory known policy bounds (`min_chain_depth` > `max_chain_depth`) abort
with no database or patch artifacts.
