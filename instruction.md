# Period-Close Control Plane

Finance hosts materialize a fiscal-window balance snapshot through `periodctl` and a oneshot systemd unit. This image ships a broken control-plane layout and a defective `periodctl` binary. Restore both so snapshots are deterministic.

## Host layout (must be restored)

- `/app/src/periodctl` must be mode `0755` and implement the CLI below.
- `/usr/local/sbin/periodctl` must be a symlink to `/app/src/periodctl` (replace the stub binary).
- `/etc/period-close/window.json` must exist as a byte-identical install of `/app/data/window.json` with mode `0644`.
- `/var/lib/period-close/` must exist as a directory with mode `0755`.
- `/etc/systemd/system/period-close.service` must remain the oneshot unit and must be mode `0644` (not world-writable). It must launch `/usr/local/sbin/periodctl` with `--window /etc/period-close/window.json` and `--snapshot /var/lib/period-close/snapshot.tsv`.

Do not modify files under `/app/data/`. Installing a copy under `/etc/period-close/` is required.

## CLI

```text
/app/src/periodctl \
  --postings <directory> \
  --accounts <tsv> \
  --window <json> \
  --snapshot <file>
```

`--postings` is `/app/data/journals/` (CSV: `posting_date,account_id,debit_cents,credit_cents,memo`). `--accounts` is `/app/data/chart.tsv` (`account_id`, `name`, `type`, `normal_balance`). `--window` may be `/app/data/window.json` or the installed `/etc/period-close/window.json` (`period_id`, `start_date`, `end_date`). Amounts are integer cents. `normal_balance` is `debit` or `credit`. Dates use `YYYY-MM-DD`.

## Snapshot semantics

An in-window posting to a registered account can produce a snapshot row `ACCOUNT_ID;balance_cents;SIDE`. An in-window posting to an unknown account fails the run with exit code `1` while still writing rows for valid known accounts. Duplicate chart IDs (case-insensitive) fail with exit code `1` and an empty snapshot. Missing arguments or unreadable paths yield exit code `2`.

Process every in-window posting from all journal CSVs. Ignore blank lines in journals and the chart. Only postings whose `posting_date` falls within `start_date`-`end_date` (inclusive) count. Trim leading and trailing ASCII whitespace from `account_id`, `debit_cents`, and `credit_cents` before validation or aggregation. Resolve `account_id` case-insensitively and emit the chart's canonical account ID.

Each in-window posting must use non-negative integer cents and exactly one non-zero side (debit or credit). Both-zero and both-nonzero rows are invalid: they fail the run with exit code `1`, but valid known-account rows from the same run still appear in the snapshot.

To prevent concurrent executions from corrupting the balance snapshot, `periodctl` must implement a concurrency lock using a lockfile at `/tmp/periodctl.lock`. If the lockfile exists, the execution checks if the recorded PID is still active; if active, it must exit with code `1`, otherwise it can overwrite/take over. The lockfile must be cleaned up on exit under all conditions (normal run or error termination). All CLI paths and arguments must be handled safely to support paths containing spaces. Journal CSV files must be parsed robustly, supporting fields (such as `memo`) that contain commas enclosed in double quotes.

For each account with in-window activity, net debits and credits according to its `normal_balance`, emit the canonical account ID with a positive magnitude and a `DR`/`CR` side marker, and exclude zero nets. Across valid in-window postings to known accounts, total debits must equal total credits or the run fails.

Write one snapshot line per account with in-window activity and a non-zero net, sorted by account ID (case-insensitive ascending).

## Snapshot format

```text
ACCOUNT_ID;balance_cents;SIDE
```

`balance_cents` is a positive integer. `SIDE` is `DR` or `CR`. One line per account; no blank lines.

## Exit codes

- `0`: balanced window and no unknown accounts
- `1`: unknown account, unbalanced totals, invalid rows, or duplicate chart IDs
- `2`: missing arguments, missing paths, or unreadable inputs
