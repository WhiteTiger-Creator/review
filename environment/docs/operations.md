# Operator notes

Use `beacon-audit acquire --case CASE --directory DIR` to acquire the pulse interval and its referenced certificate. Then use `beacon-audit verify --case CASE --directory DIR --receipt FILE` to validate the retained bytes and issue a receipt. `DIR` is the evidence directory itself, not its parent. Existing final artifacts are replaced only after a successful operation.

The verifier is deliberately strict: a missing pulse, unexpected certificate change, wrong source URI, malformed JSON, failed cryptographic check, or continuity gap prevents receipt issuance.
