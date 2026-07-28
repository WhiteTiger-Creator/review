# Authority Ranking

When documents appear to conflict, apply this order (highest first):

1. `/app/skykingdom/SCENARIO_SCHEMA.md` for input shape
2. `/app/skykingdom/API_SPEC.md` for binary surface and STATUS text
3. Subsystem rules: `FLEET_RULES.md`, `COMBAT_RULES.md`, `WEATHER_SYSTEM.md`, `SUPPLY_LOGISTICS.md`, `TECHNOLOGY_TREE.md`, `DIPLOMACY_RULES.md`, `TERRITORY_CONTROL.md`
4. `/app/skykingdom/CAMPAIGN_RULES.md` for turn lifecycle and scoring
5. `/app/docs/operator-guide.md` and `/app/docs/module-index.md` (informative)

`instruction.md` cites these paths but does not override them.
