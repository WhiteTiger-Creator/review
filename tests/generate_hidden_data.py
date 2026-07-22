"""Deterministic hidden variants for anuran-record-taxonomy-coherence."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

DATA_PATH = Path(os.environ.get("RAW_DATA_PATH", "/app/data/Frogs_MFCCs.csv"))
VARIANT = int(os.environ.get("ANURAN_VARIANT", "1"))

FEATURES = [f"MFCCs_ {i}" for i in range(1, 10)] + [f"MFCCs_{i}" for i in range(10, 23)]


def anonymize_eval_recordids(df: pd.DataFrame, seed: int) -> pd.DataFrame:
    out = df.copy()
    eval_mask = out["row_id"].astype(int) % 5 == 0
    eval_records = np.array(sorted(out.loc[eval_mask, "RecordID"].astype(int).unique()))
    rng = np.random.default_rng(seed)
    new_ids = 900000 + rng.permutation(np.arange(len(eval_records))) * 17 + seed % 1000
    mapping = dict(zip(eval_records, new_ids.astype(int)))
    out.loc[eval_mask, "RecordID"] = out.loc[eval_mask, "RecordID"].astype(int).map(mapping)
    return out


def variant_one(df: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(20260716)
    out = df.sample(frac=1.0, random_state=20260715).reset_index(drop=True)
    perm = list(FEATURES)
    rng.shuffle(perm)
    factors = np.linspace(0.91, 1.09, num=len(perm))
    for col, factor in zip(perm, factors):
        out[col] = out[col].astype(float) * factor
    out = anonymize_eval_recordids(out, 20260716)
    return out[["row_id", *perm, "Family", "Genus", "Species", "RecordID"]]


def variant_two(df: pd.DataFrame) -> pd.DataFrame:
    _ = np.random.default_rng(20260718)
    out = df.sample(frac=1.0, random_state=20260717).reset_index(drop=True)
    perm = FEATURES[::-1]
    shifts = np.linspace(-0.06, 0.06, num=len(perm))
    for col, shift in zip(perm, shifts):
        out[col] = out[col].astype(float) + shift
    scales = np.linspace(0.94, 1.06, num=len(perm))
    for col, scale in zip(perm, scales):
        out[col] = out[col].astype(float) * scale
    out = anonymize_eval_recordids(out, 20260718)
    return out[["row_id", *perm, "Family", "Genus", "Species", "RecordID"]]


def main() -> None:
    df = pd.read_csv(DATA_PATH)
    if VARIANT == 1:
        out = variant_one(df)
    elif VARIANT == 2:
        out = variant_two(df)
    else:
        raise ValueError(f"unsupported ANURAN_VARIANT={VARIANT}")
    out.to_csv(DATA_PATH, index=False)


if __name__ == "__main__":
    main()
