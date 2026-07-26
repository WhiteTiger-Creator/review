# Refinement report

Default: `/app/refinement_report.json`

Key order (exact):

```
schema_version
policy_revision
crystal_system
peak_count
admitted_count
rejected_count
chi2
rms_resid_A
a_A
b_A
c_A
alpha_deg
beta_deg
gamma_deg
rejected_ids
residuals
refine_digest
```

Nested `residuals` entries are objects in ascending `peak_id` order with key order:

```
peak_id
h
k
l
d_obs_A
d_calc_A
resid_sigma
rejected
```

- `rejected_ids`: distinct rejected `peak_id` values in ascending lexicographic order
- `rejected` inside each residual object: JSON boolean
- `chi2` / `rms_resid_A`: ordinary JSON numbers (not truncated to digest precision)
- Cell lengths `%.10f` and angles `%.8f` appear both here and in the refined structure artifact
- Residual floats `d_obs_A`, `d_calc_A`, `resid_sigma` use `%.10f`
- `refine_digest`: lowercase hex SHA-256 of the digest blob below
- Trailing newline after `}`

## Digest bytes

UTF-8 blob:

1. Line `rev:<policy_revision>`
2. For each residual row (sorted by `peak_id`): `peak_id:D_OBS:D_CALC:RESID:REJ` with `%.10f` floats and `REJ` as `0`/`1`
3. Final line `a:A:b:B:c:C:chi2:CHI2:rms:RMS` with lengths/aggregates at `%.10f`

Before emitting any `%.10f` (or `%.8f` for angles) text field used in JSON artifacts or in the digest blob: render with that printf precision, then if the rendered text is exactly `-0.0000000000` (or `-0.00000000` for angles), replace it with `0.0000000000` (or `0.00000000`). This covers IEEE signed zero and any tiny non-zero value whose ten-decimal (eight-decimal) rendering would otherwise be negative zero. Do not leave a leading minus on an all-zero fractional field.
Join lines with `\n` (no trailing blank line beyond the last content line).
