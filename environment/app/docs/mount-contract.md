Public HarborSeal contract. Candidate fixes must preserve documented semantics.
Do not mutate source fixtures. Deterministic UTC/C.UTF-8 behavior required.
Normalize destinations, last mount wins, path-component ancestry, bind-only cert sources, symlink containment.
Sibling-prefix escapes such as `/data/certs-old/file.pem` must not satisfy an allow rule for `/data/certs/file.pem`.
