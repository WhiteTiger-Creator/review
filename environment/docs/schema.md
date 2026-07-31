# Fabric graph schema

The graph is a Kuzu 0.6.1 database at `/app/graph/lacp_fabric.kuzu`.

## Node tables

### `Switch`

| property | type | meaning |
|---|---|---|
| `id` | `STRING` | primary key |
| `name` | `STRING` | the switch name used in the report |
| `system_id` | `STRING` | the switch's LACP system identifier, unique across the fabric |

### `Port`

| property | type | meaning |
|---|---|---|
| `id` | `STRING` | primary key |
| `name` | `STRING` | the port name used in the report |
| `actor_key` | `INT64` | this port's own configured aggregation key |
| `partner_system_id` | `STRING` | the `system_id` this port advertises for its partner |
| `partner_key` | `INT64` | the `actor_key` this port advertises for its partner |
| `aggregatable` | `BOOLEAN` | whether the port may join an aggregation group at all |
| `admin_up` | `BOOLEAN` | administrative state |
| `link_up` | `BOOLEAN` | physical carrier state |

`partner_system_id` and `partner_key` are local configuration on the port. They
record what the port *advertises* about the far end. Nothing in the fabric
guarantees that they describe the port actually cabled to it.

### `LagConfig`

| property | type | meaning |
|---|---|---|
| `id` | `STRING` | primary key |
| `actor_key` | `INT64` | the aggregation key this configuration governs |
| `min_links` | `INT64` | the configured minimum member count |

## Relationship tables

| relationship | endpoints | meaning |
|---|---|---|
| `HAS_PORT` | `Switch` to `Port` | port ownership; every port has exactly one owning switch |
| `HAS_LAG_CONFIG` | `Switch` to `LagConfig` | a switch's aggregation configuration |
| `LINK` | `Port` to `Port` | the physical cable between two ports |

## Structural facts

`LINK` is physical and therefore symmetric: a cable between two ports is stored
once, in one arbitrary direction only, and carries the same meaning read either
way. A port has at most one `LINK` peer. A port may have none.

`LagConfig` is per switch: two switches may hold different `min_links` for the
same `actor_key`. Every `(switch, actor_key)` pair that owns a port with that
`actor_key` has exactly one `LagConfig` on that switch.
