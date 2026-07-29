# Orbital Conjunction Contract

All distances are kilometers, velocity components are kilometers per second, and covariance entries are square kilometers. Sort output rows by `encounter_id`.

## Inputs

`orbits/encounters.csv` has one row per candidate encounter:

`encounter_id,primary_id,secondary_id,tca,rx_km,ry_km,rz_km,vx_km_s,vy_km_s,vz_km_s,cxx,cxy,cxz,cyy,cyz,czz,quality_code`

`policy/screening_policies.csv`:

`policy_id,effective_tca,status,quality_code,max_miss_km,max_sigma_distance,max_probability`

Only `approved` policies count. For an encounter, use the approved policy with the latest `effective_tca` not after `tca` and matching `quality_code`.

`policy/maneuver_blackouts.csv`:

`primary_id,start_tca,end_tca,status`

Approved blackout intervals suppress breach status for encounters whose `tca` is greater than or equal to `start_tca` and less than `end_tca`.

## Risk Rule

Let `r = (rx, ry, rz)` and `v = (vx, vy, vz)`. The encounter plane is perpendicular to `v`. Build two orthonormal axes in that plane. Project `r` and the 3x3 covariance matrix onto those axes.

If the projected covariance determinant is not positive, use probability `1` when projected miss distance is `0`; otherwise use `0`.

Otherwise:

`sigma_distance = sqrt(rp' * inverse(Cp) * rp)`

`probability = exp(-0.5 * sigma_distance^2)`

The projected miss distance is `sqrt(rp_x^2 + rp_y^2)`.

An encounter is a `BREACH` when all are true:

- not inside an approved blackout interval;
- projected miss distance is less than or equal to `max_miss_km`;
- sigma distance is less than or equal to `max_sigma_distance`;
- probability is greater than or equal to `max_probability`.

Otherwise it is `CLEAR`.

## Outputs

`encounter_risk_register.csv` columns:

`encounter_id,primary_id,secondary_id,projected_miss_km,sigma_distance,probability,blackout,decision`

Numeric fields are rounded to six decimals. Boolean fields use `TRUE` or `FALSE`.

`satellite_exposure_summary.csv` columns:

`primary_id,total_encounters,breaches,blackout_suppressed,max_probability,min_projected_miss_km`

`blackout_suppressed` is the number of encounters for that primary spacecraft whose output `blackout` value is `TRUE`, including blackout encounters that would otherwise remain `CLEAR`.

Numeric fields are rounded to six decimals.
