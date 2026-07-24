# Vaultwatch Identity Dbnode Containment Runbook

Required hardened state for any data-store platform touched by the Vaultwatch intrusion. The sync
automation provisioned itself with persistence and escalation paths that must be removed while
the dbnode is contained; the query triage rollup is not restored until the host matches this
runbook.

## SSH persistence

The automation appended its own deploy key to root's `authorized_keys`, identified by the key
comment `dbnode-sync-automation`. Revoke it: no entry carrying that comment may remain in
`/root/.ssh/authorized_keys`. The file also carries the ops on-call bastion key (comment
`ops-oncall@bastion`). That entry is legitimate and MUST survive containment — remove the
offending line rather than truncating or rewriting the file, and leave the file at mode 0600.
Locking responders out of the dbnode is a containment failure, not a containment success.

## Privilege escalation

The automation installed a temporary sudoers drop-in at `/etc/sudoers.d/dbnode-sync` granting
`svc-dbnode` passwordless root. Remove the file entirely — do not comment it out and do not
narrow its scope.

## Query key exposure

The datastore query-signing key at `/app/secrets/db_signing.key` was written world-readable. The key
is still valid and the dbnode still needs it in place: keep the file, owned `root:root`, mode
`0600`.
