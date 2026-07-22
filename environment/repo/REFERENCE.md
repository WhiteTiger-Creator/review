# PyEMD default-EMD reference

This file documents the behavior your implementation must reproduce. It is the
default configuration of the `EMD-signal` package (`from PyEMD import EMD`,
called as `EMD().emd(signal, max_imf=...)`), transcribed so you can implement it
offline without the library present. Match it to a tight floating-point
tolerance. Wherever a numeric constant, tie-break, or branch is stated here, it
is part of the contract.

The time axis `T` is the sample index: `T = [0, 1, 2, ..., n-1]`.

## Default parameters (exact values)

| name | value | role |
| --- | --- | --- |
| `nbsym` | `2` | number of extrema mirrored past each end before splining |
| extrema detector | "simple" (first-difference sign change) | how maxima/minima/zero-crossings are found |
| spline | cubic | `> 3` points → not-a-knot cubic; exactly `3` points → the special 3-point spline below |
| `MAX_ITERATION` | `1000` | hard cap on inner sifts per IMF |
| `energy_ratio_thr` | `0.2` | `check_imf` threshold |
| `std_thr` | `0.2` | `check_imf` threshold |
| `svar_thr` | `0.001` | `check_imf` threshold |
| `total_power_thr` | `0.005` | outer-loop stop threshold |
| `range_thr` | `0.001` | outer-loop stop threshold |

## Outer loop (`emd`)

Keep a running `residue = signal - sum(accepted IMFs so far)`.

1. Compute the current `residue`. Set `imf = residue.copy()`.
2. Run the **inner sift** (below) on `imf` until it is accepted or a stop is hit.
3. Append `imf` to the IMF list.
4. **Stop** the outer loop when any holds:
   - `end_condition` is true (see below), or
   - the number of accepted IMFs equals `max_imf` (only when `max_imf >= 0`).
5. After stopping, if the **last** sift ended with `extNo <= 2` (i.e. the final
   piece had at most 2 extrema and is really the trend), **drop that last IMF**
   from the list. It stays folded into the residual instead.
6. `residual = signal - sum(final IMFs)`.

If `max_imf` is negative, it imposes no cap ("as many as the decomposition
yields").

### `end_condition(signal, IMFs)`

Let `tmp = signal - sum(IMFs)`.
- if `max(tmp) - min(tmp) < range_thr` → **stop** (residue is effectively flat).
- if `sum(abs(tmp)) < total_power_thr` → **stop** (residue power is negligible).
- otherwise continue.

## Inner sift (one IMF)

Track `imf` (the current candidate) and `imf_old` (the current IMF copied at the
start of step 3c, just before the mean envelope is subtracted on this sift, so it
holds the pre-subtraction values that step 3c then updates). Iterate:

1. `iter += 1`; if `iter >= MAX_ITERATION` break (accept as-is).
2. Find extrema of `imf`. Let `extNo = #maxima + #minima`.
3. If `extNo > 2`:
   a. Build the upper envelope through the maxima and the lower envelope
      through the minima (see **envelopes**). If preparing/splining cannot
      produce envelopes (fewer than 3 extrema after mirroring), treat the piece
      as a trend: set `extNo = 2` and stop the whole decomposition.
   b. `mean[i] = 0.5 * (maxEnv[i] + minEnv[i])`.
   c. `imf_old = imf.copy()`; `imf[i] = imf[i] - mean[i]`.
   d. Recompute extrema of the new `imf`; let `extNo2 = #maxima + #minima` and
      `nzm = #zero_crossings`.
   e. Accept the IMF and break when **both**:
      - `check_imf(imf, imf_old, eMax, eMin)` is true, **and**
      - `abs(extNo2 - nzm) < 2` (extrema and zero-crossing counts agree).
4. Else (`extNo <= 2`): stop the whole decomposition (this is the trend).

### `check_imf(imf_new, imf_old, eMax, eMin)`

`eMax` / `eMin` are the prepared (mirror-extended) maxima / minima arrays used
for the envelopes; `eMax[1]` are the maxima values, `eMin[1]` the minima values.

1. If any maxima value in `eMax[1]` is `< 0` → return **false**.
2. If any minima value in `eMin[1]` is `> 0` → return **false**.
3. If `sum(imf_new^2) < 1e-10` → return **false**.
4. Let `diffSq = sum((imf_new - imf_old)^2)`.
5. `svar = diffSq / (max(imf_old) - min(imf_old))`; if `svar < svar_thr` →
   return **true**.
6. `std = sum(((imf_new - imf_old) / imf_new)^2)`; if `std < std_thr` → return
   **true**.
7. `energy_ratio = diffSq / sum(imf_old^2)`; if `energy_ratio < energy_ratio_thr`
   → return **true**.
8. otherwise return **false**.

**First-sift exception:** on the very first inner iteration `imf_old` is all
zeros. Steps 5–7 still run against that zero baseline exactly as written
(`max(imf_old) - min(imf_old)` is `0`, and `sum(imf_old^2)` is `0`); do not add
any special first-iteration guard beyond what is written here. The convergence
tests are only reached after step (3c) has produced a real `imf_old`.

## Extrema detection ("simple")

Given series `S` over `T`:

**Zero-crossings.** For `i` in `0..n-2`, record `i` where `S[i]*S[i+1] < 0`.
Additionally, if any `S[i] == 0` exactly:
- if the zeros are isolated, record each zero index;
- if there are consecutive runs of zeros, record the **middle** index of each
  run (`round((start+end)/2)`).
Sort all recorded zero-crossing indices.

**Local extrema.** Let `d[i] = S[i+1] - S[i]`. For interior `i`, a sign change
`d[i-1]*d[i] < 0` marks an extremum at `i`: a **minimum** if `d[i-1] < 0`, a
**maximum** if `d[i-1] > 0`.

**Flat plateaus.** Runs of equal samples (`d == 0`) still carry an extremum.
Detect each maximal run of zeros in `d`; drop a run that touches either end of
the array (a leading or trailing plateau is not an interior extremum). For each
remaining run with boundary slopes `dBefore` (slope just before the run) and
`dAfter` (slope just after):
- `dBefore > 0` and `dAfter < 0` → **maximum** at the run's middle index
  (`round((start+end)/2)`);
- `dBefore < 0` and `dAfter > 0` → **minimum** at the run's middle index.
Merge plateau extrema into the sorted maxima / minima lists.

## Envelopes (`extract_max_min_spline`)

1. Find extrema of `S`. If `#maxima + #minima < 3`, no envelope (signal is a
   trend).
2. Mirror-extend the extrema past both ends with `prepare_points_simple`.
3. Fit a cubic spline through the extended maxima → upper envelope; through the
   extended minima → lower envelope. Both are evaluated at every `T[i]`.

### `prepare_points_simple` (mirroring, `nbsym = 2`)

Reflect up to `nbsym` extrema across each boundary so the spline has support at
the ends. `indMax` / `indMin` are the interior maxima / minima index arrays;
`endMax`/`endMin` their lengths; `n = len(S)`.

**Left branch.** Choose the reflection center `lsym` and which extrema to mirror:

- if `indMax[0] < indMin[0]` (first extremum is a maximum):
  - if `S[0] > S[indMin[0]]`: mirror `indMax[1 : nbsym+1]` (reversed) and
    `indMin[0 : nbsym]` (reversed); `lsym = indMax[0]`.
  - else: mirror `indMax[0 : nbsym]` (reversed) and
    `indMin[0 : nbsym-1]` (reversed) with index `0` appended;
    `lsym = 0`.
- else (first extremum is a minimum):
  - if `S[0] < S[indMax[0]]`: mirror `indMax[0 : nbsym]` (reversed) and
    `indMin[1 : nbsym+1]` (reversed); `lsym = indMin[0]`.
  - else: mirror `indMax[0 : nbsym-1]` (reversed) with index `0` appended and
    `indMin[0 : nbsym]` (reversed); `lsym = 0`.

(Slice bounds are clamped to the available number of extrema. "reversed" means
the sliced indices are taken in reverse order, matching `arr[a:b][::-1]`.)

**Right branch (symmetric).** With `n-1` the last index:

- if `indMax[-1] < indMin[-1]` (last extremum is a minimum):
  - if `S[n-1] < S[indMax[-1]]`: mirror `indMax[endMax-nbsym :]` (reversed) and
    `indMin[endMin-nbsym-1 : endMin-1]` (reversed); `rsym = indMin[-1]`.
  - else: mirror `indMax[endMax-nbsym+1 :]` with `n-1` appended, all reversed,
    and `indMin[endMin-nbsym :]` (reversed); `rsym = n-1`.
- else (last extremum is a maximum):
  - if `S[n-1] > S[indMin[-1]]`: mirror `indMax[endMax-nbsym-1 : endMax-1]`
    (reversed) and `indMin[endMin-nbsym :]` (reversed); `rsym = indMax[-1]`.
  - else: mirror `indMax[endMax-nbsym :]` (reversed) and `indMin[endMin-nbsym+1 :]`
    with `n-1` appended, all reversed; `rsym = n-1`.

**Mirrored coordinates.** Reflected positions are `2*T[sym] - T[idx]`; reflected
values are `S[idx]` (the value is copied, only the time is reflected).

**Edge correction.** If after building the left set the nearest mirrored time is
**not** strictly left of `T[0]` (i.e. `tlmin[0] > T[0]` or `tlmax[0] > T[0]`),
re-mirror about `lsym = 0` instead: keep whichever of max/min was centered on an
extremum and re-slice it as `arr[0 : nbsym]` reversed, then recompute the
reflected times about `0`. Symmetrically on the right: if
`trmin[-1] < T[n-1]` or `trmax[-1] < T[n-1]`, re-mirror about `rsym = n-1`.

**Assemble.** For each of maxima and minima, concatenate
`[left-mirrored] + [interior extrema] + [right-mirrored]` for both times and
values. Then drop any column whose time equals the immediately preceding time
(dedup by position, keeping the first).

## Splines

Let the prepared extrema be `(ex, ey)` (times, values), sorted by time.

- **More than 3 points** (`len(ex) > 3`): a **not-a-knot cubic spline** —
  identical boundary conditions to `scipy.interpolate.CubicSpline` with its
  default `bc_type='not-a-knot'`. Evaluate at every `T[i]`.
- **Exactly 3 points**: the special 3-point cubic used by PyEMD
  (`cubic_spline_3pts`). It solves the 3×3 system

  ```
  [ 2/(x1-x0)          1/(x1-x0)                 0        ] [k0]   [ 3*(y1-y0)/(x1-x0)^2                      ]
  [ 1/(x1-x0)   2*(1/(x1-x0)+1/(x2-x1))    1/(x2-x1)      ] [k1] = [ 3*(y1-y0)/(x1-x0)^2 + 3*(y2-y1)/(x2-x1)^2]
  [    0              1/(x2-x1)            2/(x2-x1)      ] [k2]   [ 3*(y2-y1)/(x2-x1)^2                      ]
  ```

  for slopes `k0,k1,k2`, then on `[x0,x1]` with `t1=(t-x0)/(x1-x0)`,
  `t11=1-t1`:

  ```
  a1 =  k0*(x1-x0) - (y1-y0)
  b1 = -k1*(x1-x0) + (y1-y0)
  y(t) = t11*y0 + t1*y1 + t1*t11*(a1*t11 + b1*t1)
  ```

  and analogously on `[x1,x2]` with `a2 =  k1*(x2-x1) - (y2-y1)`,
  `b2 = -k2*(x2-x1) + (y2-y1)`. Points of `T` outside `[x0,x2]` evaluate to `0`
  (with correct mirroring they never occur, since the extended extrema straddle
  `[0, n-1]`).

- **Fewer than 3 points**: no spline (caller treats the piece as a trend).

## Edge cases to honor

- A very short or (nearly) monotonic signal may yield **no IMFs**; the whole
  signal is then returned as the residual, with an empty IMF list.
- Flat plateaus still contribute extrema (see plateau rule above).
- `imfs[k]` is a series the same length as the signal; `residual` is one such
  series. Output preserves input order.
