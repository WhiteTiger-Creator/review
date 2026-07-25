# Instrument geometry

Default path: `/app/data/sample/instrument.json`

Required keys (exact names):

```
L1_m
L2_m
two_theta_deg
pulse_offset_us
```

All values are finite JSON numbers.

- `L1_m` > 0, `L2_m` > 0
- `two_theta_deg` must satisfy `0 < two_theta_deg < 180`
- Total flight path `L_m = L1_m + L2_m`
- Bragg angle `theta_rad = deg2rad(two_theta_deg / 2)`

No other keys are required. Extra keys are ignored.
