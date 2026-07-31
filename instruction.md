The space-safety team needs a reproducible conjunction-risk review from the supplied orbital evidence bundle. Determine which close approaches breach the disclosed covariance-aware screening rule and summarize exposure by primary spacecraft.

Write the complete analysis in R at /app/analysis.R. The script must read its evidence from the directory named by ORBIT_EVIDENCE_DIR, defaulting to /app/evidence when unset. Running the script must create /app/encounter_risk_register.csv and /app/satellite_exposure_summary.csv.

Use /app/docs/orbit_contract.md for the scientific rules and output schema. The bundle contains relative encounter states, covariance terms, maneuver blackout intervals, observation-quality flags, and effective screening policies. The decision depends on encounter-plane covariance projection and coordinate-invariant risk reasoning, so base the review on the stated orbital conformance rules rather than file order.
