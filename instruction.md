# Reproduce January escalation calibration metrics (v2 postmortem audit)

Hey! Support ML needs a verified reproduction of the January ticket-escalation calibration report for the v2 postmortem audit.

The postmortem write-up at `/app/docs/incident-report-jan-escalation.md` outlines the cohort policies, class-weighting rules, temperature-scaling procedure, threshold optimization policy, and required metric definitions. Feature store seeds are located at `/app/data/featurestore.sql`, and sample scoring payload shapes are in `/app/fixtures/scoring-requests/`.

Currently, the pipeline files under `/app/src/` (including feature extraction, model training, metrics evaluation, reproduction orchestration, and standalone scoring) are incomplete or contain bugs. 

Please update and complete the pipeline in `/app/src/` so that running `npm run reproduce` compiles the TypeScript code and generates `/app/artifacts/reproduction.json`. The output report must satisfy the schema contract defined in `/app/docs/reproduction-format.md` and pass standalone request scoring via `npm run score`. Ensure all documented behaviors and edge cases (such as channel filtering, case-insensitive priority parsing, and latency scaling) are correctly handled.
