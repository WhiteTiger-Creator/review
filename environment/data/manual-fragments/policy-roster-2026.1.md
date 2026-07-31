# Policy roster fragment — authoritative 2026.1 window

The **2026.1** approval roster includes:

- alice@example.com (primary approver)
- bob@example.com (secondary approver)

Approval window for **2026.1**: **2026-01-05** through **2026-03-01** (exclusive end not applicable; both bounds inclusive UTC).

Commits carrying `config/signing-policy.yaml` for version **2026.1** must include an `Approved-By:` trailer naming a roster principal and must be timestamped inside this window.

Supersession: emergency policy **2025.12** was superseded by **2026.1** effective **2026-01-05T00:00:00Z**.
