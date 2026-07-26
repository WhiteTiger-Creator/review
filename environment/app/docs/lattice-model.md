# Lattice refinement model

Neutron powder diffraction lattice refinement for materials crystallography: convert time-of-flight Bragg peaks to observed d-spacings, form crystal-system Q-space design rows on the reciprocal metric, and recover direct-cell lengths by weighted least squares.

## Constants from policy

Use `h_js` and `m_n_kg` from the live refine policy (never hardcode alternate CODATA sets).

## TOF → observed d-spacing

For each peak:

```
t_s = (tof_us - pulse_offset_us) * 1e-6
sigma_t_s = sigma_tof * 1e-6
L_m = L1_m + L2_m
theta_rad = deg2rad(two_theta_deg / 2)
d_m = h_js * t_s / (2 * L_m * sin(theta_rad) * m_n_kg)
sigma_d_m = h_js * sigma_t_s / (2 * L_m * sin(theta_rad) * m_n_kg)
d_obs_A = d_m * 1e10
sigma_d_A = sigma_d_m * 1e10
```

Work in Q-space: `Q_obs = 1 / d_obs_A^2`. Propagate:

```
sigma_Q = 2 * sigma_d_A / d_obs_A^3
w_base = 1 / sigma_Q^2
```

## Admission / extinction

`admit_mode`:

- `intensity_floor`: primary-reject when `intensity < intensity_floor`
- `intensity_and_extinction`: primary-reject when `intensity < intensity_floor`, or when `extinct_flag == 1` and `extinction_mode == "skip"`

`extinction_mode`:

- `skip`: extinct peaks are primary-rejected under `intensity_and_extinction`
- `downweight`: extinct peaks stay admitted; multiply weight by `extinction_scale` (must be in `(0,1]`)

Primary-rejected peaks do not enter the normal equations.

## Crystal-system design rows

Unknowns are free reciprocal-metric components. Observed equation `Q_obs ≈ row · x`.

| system | `x` | row |
| --- | --- | --- |
| `cubic` | `[X]` with `X=1/a^2` | `[h^2+k^2+l^2]` |
| `tetragonal` | `[X,Z]` | `[h^2+k^2, l^2]` |
| `orthorhombic` | `[X,Y,Z]` | `[h^2, k^2, l^2]` |
| `hexagonal` | `[X,Z]` | `[(4/3)*(h^2 + h*k + k^2), l^2]` |

Recover direct lengths: `a = 1/sqrt(X)` (and `b`,`c` analogously). Locked angles come from the structure table. For cubic/tetragonal/hexagonal, copy locked equal-axis lengths from the free axis after recovery.

## Weighted least squares

Solve `x = (A' W A)^{-1} A' W q` with diagonal `W` from admitted weights. Require at least `min_admitted_peaks` admitted peaks and a positive-definite normal matrix.

## Residual triage and one re-fit

For every peak (including primary-rejected), compute `d_calc_A` from the current cell and Miller indices:

- cubic/tetragonal/orthorhombic: `d_calc = 1 / sqrt((h/a)^2 + (k/b)^2 + (l/c)^2)`
- hexagonal: `d_calc = 1 / sqrt((4/3)*(h^2+h*k+k^2)/a^2 + l^2/c^2)`

`resid_sigma = (d_obs_A - d_calc_A) / sigma_d_A`

Mark `residual_reject` when the peak was not primary-rejected and `abs(resid_sigma) > residual_sigma_max`.

`rejected = primary_reject OR residual_reject`.

If any `residual_reject` occurred on that first pass, rebuild the admitted set as peaks with `rejected == false` and solve the normal equations once more (single re-fit only). After that re-fit:

1. Recompute `d_calc_A` and `resid_sigma` for **every** peak against the **final** cell.
2. **Re-evaluate** `residual_reject` from those final residuals (same threshold rule). Peaks that failed the threshold against the distorted first cell but pass against the final cell must be cleared (`residual_reject = false`, and `rejected` follows). Primary rejects never clear.
3. Do not run a second re-fit even if the refreshed flags still show residual rejects.

Final `rejected_ids`, `admitted_count`, `chi2`, `rms_resid_A`, residual rows, and `refine_digest` must use the refreshed flags after this re-evaluation.

## Aggregates

```
chi2 = sum over final-admitted peaks of (resid_sigma^2)
rms_resid_A = sqrt(mean over final-admitted peaks of (d_obs_A - d_calc_A)^2)
```

If zero peaks remain admitted after triage, that is fatal.
