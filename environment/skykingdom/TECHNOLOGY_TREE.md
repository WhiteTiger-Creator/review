# Technology Tree

This document is normative for research costs, prerequisites, and combat/movement effects.

## Catalog

Exact tech IDs in catalog order:

| tech | cost_aetherium | cost_crystal | prerequisite | effect |
| --- | ---: | ---: | --- | --- |
| LATTICE_SAILS | 20 | 0 | (none) | tech_range_bonus += 1 |
| AETHER_INJECTORS | 25 | 10 | LATTICE_SAILS | tech_fuel_discount_pct += 10 |
| HARPOON_BALLISTA | 30 | 15 | (none) | tech_atk_pct += 10 |
| SKYIRON_PLATING | 30 | 15 | (none) | tech_def_pct += 10 |
| STORMSEER_LENS | 40 | 25 | AETHER_INJECTORS | tech_atk_pct += 5 and tech_def_pct += 5 |
| CROWN_DOCKS | 50 | 30 | SKYIRON_PLATING | depot fuel_income += 2 for that kingdom |

Effects stack additively for a kingdom when the tech is present in `kingdom.researched` (array of tech ids).

## RESEARCH command

`RESEARCH <tech>` is legal for the player kingdom when:

1. Campaign state is `running`.
2. Tech id exists in the catalog.
3. Tech is not already researched by the player kingdom.
4. Prerequisite is empty or already researched.
5. Treasury can pay both costs simultaneously.

On success, subtract costs, append tech id to `researched` (catalog order is not required in the array; membership matters), and append the normalized command to history.

## Combat application

```text
tech_atk_pct = sum of atk percent effects
tech_def_pct = sum of def percent effects
atk = floor(atk * (100 + tech_atk_pct) / 100)
def = floor(def * (100 + tech_def_pct) / 100)
```

These apply at step 4 of the COMBAT_RULES.md pipeline.

## Movement application

`tech_range_bonus` and `tech_fuel_discount_pct` apply as named in FLEET_RULES.md and SUPPLY_LOGISTICS.md.
