Public HarborSeal contract. Candidate fixes must preserve documented semantics.
Do not mutate source fixtures. Deterministic UTC/C.UTF-8 behavior required.
Only approved OpenSSL env vars may influence profiles; disallowed OPENSSL_CONF/MODULES are ignored.
Process environment entries split at the first equals sign so values may contain `=`; duplicate keys keep the last occurrence (for example `OPENSSL_CONF` and `PATH`).
