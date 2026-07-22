# MLflow deployment stack: advisory risk report

Methodology revision 4. Maintained by the platform security group.

## Purpose

Ranks the third party packages of the MLflow deployment stack by advisory
exposure so patch work is ordered by risk. The report is regenerated from two
inputs only: the deployment documentation set and the offline OSV advisory
mirror. It must be reproducible from those inputs alone.

## Inputs

- Documentation inventory: every `.md` page under `/app/docs/pages`.
- Advisory mirror: every `.json` record under `/var/lib/osv`, OSV schema 1.6.

## Package inventory

A package pin is a token of the form `name==version` inside a fenced code
block of a documentation page. Names compare case insensitively and are
reported lowercase. Versions are dotted numerics.

`pages_referenced` for a package is the number of distinct pages that pin it
at any version.

The assessed version of a package is the lowest version pinned anywhere in
the inventory. Deployments are assumed to run the oldest version still
documented, so the assessment is conservative.

## Advisory matching

A mirror record applies to a package when one of its `affected` entries names
the package in the `PyPI` ecosystem and the assessed version is affected:
listed in the entry's `versions` array, or inside an `ECOSYSTEM` range, at or
above `introduced` (the literal `0` means no lower bound), strictly below
`fixed`, and at or below `last_affected`. Records carrying a `withdrawn`
timestamp are ignored entirely.

## Vulnerability identity

Records sharing an identity describe one vulnerability. Two records share an
identity when either lists the other's `id` among its `aliases`, or when
their alias sets overlap, directly or through intermediate records. Each such
group counts once: `advisory_count` is the number of groups, not the number
of mirror records.

Each group is reported under one canonical id: the smallest `PYSEC-` member
id when the group has one, otherwise the smallest member id, in byte order.
The `advisories` array lists the canonical ids in ascending byte order.

## Severity

A record's severity is the CVSS v3.1 base score computed from its `CVSS_V3`
vector. Records without a vector fall back to the `database_specific`
severity label: CRITICAL is 9.5, HIGH is 7.8, MODERATE is 5.4, LOW is 2.1.

When a group contains `PYSEC-` records, the group severity is the highest
severity among those records; the Python security team's assessment
supersedes mirrored GHSA scoring. Otherwise the group severity is the
highest severity among all members. `max_severity` for a package is the
highest group severity across its groups.

## Risk score

    risk_score = max_severity + 0.4 * (advisory_count - 1)
               + 0.2 * pages_referenced

capped at 10.0. Every term is exact in tenths, so scores carry one decimal
digit and no floating point rounding is involved.

## Report

Packages with no matching vulnerability group are omitted. Entries are
ordered by `risk_score` descending; ties order by `advisory_count`
descending, then by `name` ascending. The report is emitted as JSON
conforming to `/app/schema/risk-report.schema.json`, with `schema_version`
`"4"`.

## Revision history

- r4, 2026-06: methodology revised after the Q2 security review; reports
  produced by r3 tooling are not comparable.
- r3, 2025-11: added `pages_referenced` weighting.
- r2, 2025-04: first automated generation.
