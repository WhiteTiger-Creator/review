The Cargo workspace under `/app` ships optional native backends behind Cargo features. A plain default build succeeds. The documented matrix in `/app/contracts/matrix_arms.json` currently produces arms that fail their ABI/layout probe, or record disagreeing layout fingerprints across arms that share a backend.

Every documented arm must build with its documented command. The integration probe for each arm must exit 0. Arms that share a backend feature must record the same layout fingerprint in `/app/output/matrix_report.json`. Linking with silent fingerprint skew is a failure. Do not delete arms, strip features to shrink the matrix, or ship only the default-feature build.

Rebuild from the workspace sources and produce the report via `/app/scripts/run_matrix.sh`. Hand-written JSON without rebuilt artifacts is insufficient. Report shape is in `/app/contracts/report_schema.md` (`schema_version` is 1, plus `arms` and `shared_backend_digests`).
