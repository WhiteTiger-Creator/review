"""Shared digest helpers for replay tooling and offline checks."""
from __future__ import annotations

import hashlib


def row_material_digest(rows: list[dict], bank_fingerprint: str = "") -> str:
    ordered = sorted(rows, key=lambda r: (r["row_seq"], r["instance_key"], r["corpus_tag"]))
    material = "".join(
        f'{r["row_seq"]}|{r["instance_key"]}|{r["duty_cycles"]}|{r["corpus_tag"]}|{r["lane_phase"]};'
        for r in ordered
    )
    material += f"#bf|{bank_fingerprint}"
    return hashlib.sha256(material.encode()).hexdigest()[:8]


def journal_duty_checksum(rows: list[dict]) -> str:
    ordered = sorted(rows, key=lambda r: (r["instance_key"], r["corpus_tag"]))
    material = "".join(
        f'{r["instance_key"]}:{r["corpus_tag"]}:{r["duty_cycles"]};'
        for r in ordered
    )
    return hashlib.sha256(material.encode()).hexdigest()[:8]


def bank_fp_material(epoch: int, od_bias: int, profile_word: int) -> str:
    material = f"{epoch}|{od_bias}|{profile_word:x}"
    return hashlib.sha256(material.encode()).hexdigest()[:8]
