# Binary blob layouts

Little-endian packing throughout.

## WAVE incident blob

| offset | field | type |
|--------|-------|------|
| 0 | magic | 4 bytes, `WAVE` |
| 4 | row_count | uint16 |
| 6 | rows | `row_count` field bytes |

## CELL unit slice blob

| offset | field | type |
|--------|-------|------|
| 0 | magic | 4 bytes, `CELL` |
| 4 | version | uint8 |
| 5 | arm_count | uint8 |
| 6 | arms | `arm_count` arm records |

## Arm record (6 bytes)

| offset | field | type |
|--------|-------|------|
| 0 | id | uint8 |
| 1 | kind | uint8 |
| 2 | mask | uint16 |
| 4 | shadow_link | uint8 |
| 5 | sequence | uint8 |

Kind `1` is include; kind `2` is exclude.

## Ledger wave record (NDJSON)

Each line in `pack/ledger/waves.ndjson` holds one wave record.

| field | type | notes |
|-------|------|-------|
| gen | integer | restart wave generation |
| family | string | wave family hint |
| unit | string | unit slice stem hint |
| tomb | boolean | when true, record must not advance tip |

## Gen-bound staging checkpoint

`pack/checkpoints/stg_g{N}.bin` holds at least eight bytes used as the staged-anchor prefix for overlay generation N when present.
