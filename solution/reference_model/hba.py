"""HBA ordering, containment, and shadow detection."""

from __future__ import annotations

import ipaddress
from typing import Any


def cidr_width(cidr: str | None) -> int:
    if cidr is None:
        return -1
    return int(ipaddress.IPv4Network(cidr, strict=False).prefixlen)


def db_selector_rank(sel: str) -> int:
    return 0 if sel == "all" else 1


def role_selector_rank(sel: str) -> int:
    return 0 if sel == "all" else 1


def connection_class_rank(ct: str) -> int:
    return {"local": 0, "host": 1, "hostssl": 2}[ct]


def db_contains(outer: str, inner: str) -> bool:
    if outer == "all":
        return True
    return outer == inner


def role_contains(outer: str, inner: str) -> bool:
    if outer == "all":
        return True
    return outer == inner


def address_contains(outer: dict[str, Any], inner: dict[str, Any]) -> bool:
    otype = outer["connection_type"]
    itype = inner["connection_type"]
    if otype == "local":
        return itype == "local"
    if otype == "host":
        if itype != "host":
            return False
    elif otype == "hostssl":
        if itype != "hostssl":
            return False
    else:
        return False
    oc = outer.get("ipv4_cidr_or_null")
    ic = inner.get("ipv4_cidr_or_null")
    if oc is None or ic is None:
        return False
    return ipaddress.IPv4Network(oc, strict=False).supernet_of(
        ipaddress.IPv4Network(ic, strict=False)
    )


def connection_class_contains(outer: str, inner: str) -> bool:
    if outer == "local":
        return inner == "local"
    if outer == "host":
        return inner == "host"
    if outer == "hostssl":
        return inner == "hostssl"
    return False


def hba_sort_key(row: dict[str, Any]) -> tuple:
    mandatory_reject = (
        0 if (row.get("mandatory") and row["auth_method"] == "reject") else 1
    )
    cidr = row.get("ipv4_cidr_or_null")
    cidr_w = cidr_width(cidr) if cidr else -1
    source_rank = 0 if row.get("source") == "policy" else 1
    return (
        mandatory_reject,
        db_selector_rank(row["database_selector"]),
        role_selector_rank(row["role_selector"]),
        -cidr_w if cidr else 0,
        -connection_class_rank(row["connection_type"]),
        source_rank,
        -row["priority"],
        row["hba_id"],
    )


def order_hba_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=hba_sort_key)


def find_shadow(rows: list[dict[str, Any]]) -> tuple[str, str] | None:
    ordered = order_hba_rows(rows)
    for i, later in enumerate(ordered):
        for earlier in ordered[:i]:
            if (
                connection_class_contains(
                    earlier["connection_type"], later["connection_type"]
                )
                and db_contains(
                    earlier["database_selector"], later["database_selector"]
                )
                and role_contains(earlier["role_selector"], later["role_selector"])
                and address_contains(earlier, later)
            ):
                return later["hba_id"], earlier["hba_id"]
    return None
