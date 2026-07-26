# Operator Guide

Sky Kingdom Fleet Campaign is an offline Go campaign simulator. Implement the module under `/app/skykingdom` using the normative `*_RULES.md`, `*_SYSTEM.md`, `TECHNOLOGY_TREE.md`, `SCENARIO_SCHEMA.md`, and `API_SPEC.md` files in that directory.

Build with `go build -o skykingdom .` from `/app/skykingdom`. Use `skykingdom play` for interactive campaigns and `skykingdom eval` for machine checks.

Sample scenarios under `/app/skykingdom/scenarios` demonstrate schema only. Hidden evaluations use other legal scenarios.
