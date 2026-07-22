# SQL serialization

Write `bootstrap.sql` first, then compute `sql_sha256` over its exact bytes,
then write `bootstrap_plan.json`. On fatal failure remove both outputs and any
temporary files.

## Quoting

Identifier quoting: wrap in double quotes; replace each internal `"` with `""`.

String-literal quoting: wrap in single quotes; replace each internal `'` with
`''`.

## Setting literals

- integer: base-10 without leading plus
- boolean: `'on'` or `'off'`
- string: single-quoted
- string_array: sort and deduplicate UTF-8, join with commas and no spaces,
  emit as one single-quoted string

## Statement templates

Create role (one line, attributes in this order):

```text
CREATE ROLE <quoted-role-name> WITH LOGIN|NOLOGIN INHERIT|NOINHERIT CREATEDB|NOCREATEDB CREATEROLE|NOCREATEROLE REPLICATION|NOREPLICATION BYPASSRLS|NOBYPASSRLS CONNECTION LIMIT <integer>;
```

Membership:

```text
GRANT <quoted-granted-role> TO <quoted-member-role>;
```

Alter system:

```text
ALTER SYSTEM SET <quoted-setting-name> = <canonical-setting-literal>;
```

Create database (one line):

```text
CREATE DATABASE <quoted-database-name> WITH OWNER = <quoted-owner-role-name> TEMPLATE = <quoted-template> ENCODING = <string-literal> CONNECTION LIMIT = <integer>;
```

Connect (no semicolon):

```text
\connect <quoted-database-name>
```

Create extension (one line):

```text
CREATE EXTENSION IF NOT EXISTS <quoted-extension-id> WITH VERSION <string-literal>;
```

Privileges:

```text
GRANT <comma-space privileges> ON DATABASE <quoted-db> TO <quoted-role>[ WITH GRANT OPTION];
GRANT <comma-space privileges> ON SCHEMA <quoted-schema> TO <quoted-role>[ WITH GRANT OPTION];
GRANT <comma-space privileges> ON TABLE <quoted-schema>.<quoted-table> TO <quoted-role>[ WITH GRANT OPTION];
```

Settings:

```text
ALTER DATABASE <quoted-db> SET <quoted-name> = <literal>;
ALTER ROLE <quoted-role> SET <quoted-name> = <literal>;
ALTER ROLE <quoted-role> IN DATABASE <quoted-db> SET <quoted-name> = <literal>;
```

HBA comment (one line; use `-` when CIDR is null):

```text
-- PG_HBA <connection_type> <database_selector> <role_selector> <ipv4_cidr_or_dash> <auth_method> id=<hba_id> source=<source>
```

Reload:

```text
SELECT pg_reload_conf();
```

Do not emit a restart statement.

## Phase serialization

Transactional phase:

```text
-- PHASE <phase_index> <phase_kind> cluster=<cluster_id>
BEGIN;
<statements>
COMMIT;
```

Nontransactional phase:

```text
-- PHASE <phase_index> <phase_kind> cluster=<cluster_id>
<statements>
```

Database transaction phase places `\connect` immediately after the phase
comment and before `BEGIN`.

Separate phases with exactly one blank line. No leading blank line. Exactly one
trailing LF. Emit accepted clusters in `cluster_id` order. Emit no SQL for
rejected clusters.

`sql_sha256` covers the exact final file bytes, including the trailing LF.
