# Orbital Conjunction Contract

All distances are kilometers, velocity components are kilometers per second, and covariance entries are square kilometers. Sort output rows by `encounter_id`.

## Inputs

`orbits/encounters.csv` has one row per candidate encounter:

`encounter_id,primary_id,secondary_id,tca,rx_km,ry_km,rz_km,vx_km_s,vy_km_s,vz_km_s,cxx,cxy,cxz,cyy,cyz,czz,quality_code`

`policy/screening_policies.csv`:

`policy_id,effective_tca,revision_ts,status,quality_code,max_miss_km,max_sigma_distance,max_probability,covariance_scale,hard_body_radius_m,probability_floor`

Only `approved` policies count. For an encounter, use the approved policy with matching `quality_code` and the latest `effective_tca` not after `tca`. If more than one approved matching policy has that same latest `effective_tca`, use the row with the latest `revision_ts`; if that is still tied, use the lexicographically greatest `policy_id`.

`policy/maneuver_blackouts.csv`:

`primary_id,start_tca,end_tca,status`

Approved blackout intervals suppress breach status for encounters whose `tca` is greater than or equal to `start_tca` and less than `end_tca`.

## Risk Rule

Let `r = (rx, ry, rz)` and `v = (vx, vy, vz)`. The encounter plane is perpendicular to `v`. Build two orthonormal axes in that plane. Multiply every entry of the encounter's 3x3 covariance matrix by the selected policy's `covariance_scale`, then project `r` and the scaled covariance matrix onto the encounter-plane axes.

Let `hard_body_radius_km = hard_body_radius_m / 1000`. If the projected covariance determinant is not positive, use probability `1` when projected miss distance is `0`; otherwise use `0`.

Otherwise:

`sigma_distance = sqrt(rp' * inverse(Cp) * rp)`

Approximate the hard-body disk probability by fixed polar quadrature over the disk centered at the encounter-plane origin. Use radial nodes `0.1127016654, 0.5, 0.8872983346` with radial weights `5/18, 8/18, 5/18`, and 12 equally spaced angles `theta_j = 2 * pi * j / 12` for `j = 0..11`. For each radial node `rho` and angle `theta`, define `y = hard_body_radius_km * rho * (cos(theta), sin(theta))`, `delta = y - rp`, and `density(y) = exp(-0.5 * delta' * inverse(Cp) * delta) / (2 * pi * sqrt(det(Cp)))`.

`disk_mass = sum(radial_weight * (2 * pi / 12) * hard_body_radius_km^2 * radial_node * density(y))`

`probability = min(1, disk_mass + probability_floor)`

The projected miss distance is `sqrt(rp_x^2 + rp_y^2)`.

For the probability breach comparison, compute `age_hours` as the elapsed hours from the selected policy's `effective_tca` to the encounter `tca`. Let `policy_probability_threshold = max_probability * (1 + min(0.25, 0.015 * floor(age_hours / 6)))`.

An encounter is a `BREACH` when all are true:

- not inside an approved blackout interval;
- projected miss distance is less than or equal to `max_miss_km`;
- sigma distance is less than or equal to `max_sigma_distance`;
- probability is greater than or equal to `policy_probability_threshold`.

Otherwise it is `CLEAR`.

## Outputs

`encounter_risk_register.csv` columns:

`encounter_id,primary_id,secondary_id,projected_miss_km,sigma_distance,probability,blackout,decision`

The `projected_miss_km`, `sigma_distance`, and `probability` fields are rounded and formatted with exactly six digits after the decimal point, including trailing zeros. Boolean fields use `TRUE` or `FALSE`.

`satellite_exposure_summary.csv` columns:

`primary_id,total_encounters,breaches,blackout_suppressed,max_probability,min_projected_miss_km`

`blackout_suppressed` is the number of encounters for that primary spacecraft whose output `blackout` value is `TRUE`, including blackout encounters that would otherwise remain `CLEAR`.

The `total_encounters`, `breaches`, and `blackout_suppressed` fields are plain base-ten integers with no decimal point. The `max_probability` and `min_projected_miss_km` fields are rounded and formatted with exactly six digits after the decimal point, including trailing zeros.
