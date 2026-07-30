# Redaction contract

The analyzer may use raw OAuth token fingerprints internally to correlate issuance, use, forwarding, revocation, and refresh replay events. Raw token fingerprint strings from the input event corpus are sensitive material and must never appear in published JSON or DOT output.

A raw token fingerprint is any nonempty string value read from an event payload key named `token_fingerprint`, `parent_token_fingerprint`, `child_token_fingerprint`, `access_token_fingerprint`, or `refresh_token_fingerprint`.

When a token fingerprint must be displayed in a finding, graph node label, graph edge label, rejected-candidate explanation, or legacy compatibility field, emit the redacted token label:

```text
tok_ + first eight characters of the raw fingerprint string
```

For example, raw fingerprint `fp_access_alice_01` is displayed as `tok_fp_acces`.

The redaction is display-only. Correlation, deduplication, revocation-lag matching, refresh-family matching, and chain construction still use the raw internal value before publication.

The published report and DOT graph must not contain any raw token fingerprint string or any longer substring that reveals more than the `tok_` plus eight-character label.
