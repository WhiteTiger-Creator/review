# Incident INF-4412 — lost policy after history rewrite

During the March 2026 deploy branch cleanup, `config/signing-policy.yaml` was removed from `HEAD` while unreachable commits and reflog entries were preserved for forensic recovery.

Operators must not trust recency-based recovery. Cross-reference candidate commit IDs documented in `config/POLICY_BOOTSTRAP.md` with this manual's approval roster and supersession tables.

Authorized recovery target: policy version **2026.1** with `Approved-By: alice@example.com` inside the **2026.1** approval window.

Unauthorized examples preserved for negative testing:

- **2025.12** emergency policy (superseded)
- **2026.99** permissive draft (`Approved-By: nobody@example.com`)
