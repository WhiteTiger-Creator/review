Public HarborSeal contract. Candidate fixes must preserve documented semantics.
Do not mutate source fixtures. Deterministic UTC/C.UTF-8 behavior required.
Profiles: default, fips (with base+fips+default_properties), legacy_full, legacy_verify_only.
Legacy verification profiles emit `hs_legacy` provider sections without enabling generation.
