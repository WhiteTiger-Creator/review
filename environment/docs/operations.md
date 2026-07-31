# Ledger gateway runtime operations

The gateway runs from a relocatable offline service root rather than being installed on the host. `rebuild-runtime ROOT` refreshes the native gateway from `/app`, stages below `ROOT/opt/ledger/releases`, and rehearses both loader modes before activation. `ROOT` may contain spaces, must be an absolute path other than `/`, and must not resolve through a symbolic-link component. Release slots are addressed by release name and content identity. Refreshing identical healthy content leaves both active links unchanged.

`/opt/ledger/current` is the stable process path and `/opt/ledger/previous` is the single verified rollback point. Both are relative links into the release directory. A changed release moves current to previous only when the old release still passes the full trust check. Abandoned candidates, rejected trees, and slots other than current and previous are removed after a successful operation.

Execution, refresh, and rollback use `ROOT/var/lock/ledger-runtime.lock` as one lock domain. A runner holds a read lease from trust verification until its native process exits. Refresh and rollback take the write lease before recovery or mutation, so cleanup cannot remove a release still in use.

Activation is crash recoverable. `LEDGER_REBUILD_FAIL=before-promote` exits nonzero after rehearsal without changing active state. `LEDGER_REBUILD_FAIL=after-current` exits nonzero after the new current link is visible but before its predecessor is published; `ROOT/var/lib/ledger/activation.pending` then records enough relative-link state for the next refresh or rollback to finish the interrupted activation. A valid current remains runnable in either case. No pending record remains after a successful operation.

`rollback-runtime ROOT` first resolves an interrupted activation, then verifies and swaps the two active links, rebuilds the cache, and rehearses both modes. A missing or untrusted previous release leaves current untouched.

`run-runtime ROOT MODE REQUEST` accepts `baseline` or `v3` and the request catalog in the release layout contract. It verifies the active manifest, content identity, attestation, provenance, and exact payload before entering the chroot. Path-like names, malformed metadata, missing or changed files, unlisted regular files, link escapes, and a replaced trust statement are errors.

Bring-up can be checked in three passes. First confirm both native stacks and the content-addressed payload. Next confirm that execution rejects payload drift and untrusted metadata. Only then exercise promotion faults, rollback, and the drain lock. Interface mistakes may use normal usage errors. A payload trust failure must return nonzero and include `integrity`; an untrusted signature must include `signature`. A pre-promotion fault must preserve the old active release, and its abandoned candidate must be gone after the next successful writer operation.

Root arguments are lexical contracts as well as filesystem checks. They must already be absolute and normalized, so explicit `.` or `..` components are rejected even if resolving them would produce the same directory. Existing symbolic-link components are also rejected.

Baseline suppresses glibc hardware-capability selection. The v3 mode bypasses the cache and explicitly prepends `x86-64-v3`. Loader-control variables supplied by the caller do not reach the chrooted process. Direct loader invocation against an intact current release produces the same native selection as the wrapper.
