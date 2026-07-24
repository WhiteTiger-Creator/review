"""Canonical PostgreSQL SQL serialization."""

from __future__ import annotations

from typing import Any


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def quote_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def setting_literal(value: Any, setting_name: str, value_type: str) -> str:
    if value_type == "integer":
        return str(int(value))
    if value_type == "boolean":
        return "'on'" if value else "'off'"
    if value_type == "string":
        return quote_string(str(value))
    if value_type == "string_array":
        items = sorted(set(str(x) for x in value), key=lambda s: s.encode("utf-8"))
        joined = ",".join(items)
        return quote_string(joined)
    raise ValueError(f"unknown value type {value_type}")


def grant_option_suffix(grant_option: bool) -> str:
    return " WITH GRANT OPTION" if grant_option else ""


PRIVILEGE_ORDER = ["CONNECT", "CREATE", "USAGE", "SELECT", "INSERT", "UPDATE", "DELETE"]


def sort_privileges(privs: list[str]) -> list[str]:
    order = {p: i for i, p in enumerate(PRIVILEGE_ORDER)}
    return sorted(privs, key=lambda p: order[p])


def create_role_sql(role: dict[str, Any]) -> str:
    attrs = []
    attrs.append("LOGIN" if role["login"] else "NOLOGIN")
    attrs.append("INHERIT" if role["inherit"] else "NOINHERIT")
    attrs.append("CREATEDB" if role["createdb"] else "NOCREATEDB")
    attrs.append("CREATEROLE" if role["createrole"] else "NOCREATEROLE")
    attrs.append("REPLICATION" if role["replication"] else "NOREPLICATION")
    attrs.append("BYPASSRLS" if role["bypassrls"] else "NOBYPASSRLS")
    attrs.append(f"CONNECTION LIMIT {role['connection_limit']}")
    return f"CREATE ROLE {quote_ident(role['role_name'])} WITH {' '.join(attrs)};"


def grant_membership_sql(granted: str, member: str) -> str:
    return f"GRANT {quote_ident(granted)} TO {quote_ident(member)};"


def alter_system_sql(setting_name: str, literal: str) -> str:
    return f"ALTER SYSTEM SET {quote_ident(setting_name)} = {literal};"


def create_database_sql(db: dict[str, Any], owner_name: str) -> str:
    return (
        f"CREATE DATABASE {quote_ident(db['database_name'])} WITH OWNER = "
        f"{quote_ident(owner_name)} TEMPLATE = {quote_ident(db['template'])} ENCODING = "
        f"{quote_string(db['encoding'])} CONNECTION LIMIT = {db['connection_limit']};"
    )


def connect_directive(db_name: str) -> str:
    return f"\\connect {quote_ident(db_name)}"


def create_extension_sql(ext_id: str, version: str) -> str:
    return (
        f"CREATE EXTENSION IF NOT EXISTS {quote_ident(ext_id)} WITH VERSION "
        f"{quote_string(version)};"
    )


def grant_database_sql(
    privs: list[str], db_name: str, role_name: str, grant_option: bool
) -> str:
    joined = ", ".join(sort_privileges(privs))
    return (
        f"GRANT {joined} ON DATABASE {quote_ident(db_name)} TO "
        f"{quote_ident(role_name)}{grant_option_suffix(grant_option)};"
    )


def grant_schema_sql(
    privs: list[str], schema: str, role_name: str, grant_option: bool
) -> str:
    joined = ", ".join(sort_privileges(privs))
    return (
        f"GRANT {joined} ON SCHEMA {quote_ident(schema)} TO "
        f"{quote_ident(role_name)}{grant_option_suffix(grant_option)};"
    )


def grant_table_sql(
    privs: list[str], schema: str, table: str, role_name: str, grant_option: bool
) -> str:
    joined = ", ".join(sort_privileges(privs))
    return (
        f"GRANT {joined} ON TABLE {quote_ident(schema)}.{quote_ident(table)} TO "
        f"{quote_ident(role_name)}{grant_option_suffix(grant_option)};"
    )


def alter_database_setting_sql(db_name: str, setting_name: str, literal: str) -> str:
    return f"ALTER DATABASE {quote_ident(db_name)} SET {quote_ident(setting_name)} = {literal};"


def alter_role_setting_sql(role_name: str, setting_name: str, literal: str) -> str:
    return f"ALTER ROLE {quote_ident(role_name)} SET {quote_ident(setting_name)} = {literal};"


def alter_role_database_setting_sql(
    role_name: str, db_name: str, setting_name: str, literal: str
) -> str:
    return (
        f"ALTER ROLE {quote_ident(role_name)} IN DATABASE {quote_ident(db_name)} SET "
        f"{quote_ident(setting_name)} = {literal};"
    )


def hba_comment(row: dict[str, Any]) -> str:
    cidr = row.get("ipv4_cidr_or_null") or "-"
    return (
        f"-- PG_HBA {row['connection_type']} {row['database_selector']} "
        f"{row['role_selector']} {cidr} {row['auth_method']} "
        f"id={row['hba_id']} source={row['source']}"
    )


def reload_sql() -> str:
    return "SELECT pg_reload_conf();"


def serialize_phases(phases: list[dict[str, Any]], cluster_id: str) -> str:
    lines: list[str] = []
    for phase in phases:
        if lines:
            lines.append("")
        idx = phase["phase_index"]
        kind = phase["phase_kind"]
        lines.append(f"-- PHASE {idx} {kind} cluster={cluster_id}")
        if kind == "database_transaction":
            lines.append(phase["connect_line"])
            lines.append("BEGIN;")
            lines.extend(phase["statements"])
            lines.append("COMMIT;")
        elif phase.get("transactional"):
            lines.append("BEGIN;")
            lines.extend(phase["statements"])
            lines.append("COMMIT;")
        else:
            lines.extend(phase["statements"])
    if not lines:
        return ""
    return "\n".join(lines) + "\n"
