# Peaks table

Default path: `/app/data/sample/peaks.csv`

Exact header order:

```
peak_id,h,k,l,tof_us,intensity,sigma_tof,extinct_flag
```

Rules:

- `peak_id`: non-empty unique string
- `h`,`k`,`l`: integers; at least one of `|h|+|k|+|l|` must be > 0
- `tof_us`: finite float; must be strictly greater than `pulse_offset_us` from the instrument file
- `intensity`: finite float ≥ 0
- `sigma_tof`: finite float > 0
- `extinct_flag`: integer `0` or `1`
- Pack must contain ≥ 1 data row

Rows may arrive in any order. Residual tables are always emitted sorted by ascending `peak_id` (lexicographic).
