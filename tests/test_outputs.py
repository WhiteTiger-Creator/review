"""Deterministic verifier for anuran-record-taxonomy-coherence."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import log_loss

OUTPUT_DIR = Path(os.environ.get("AGENT_OUTPUT_DIR", "/home/output"))
DATA_DIR = Path(os.environ.get("RAW_DATA_DIR", "/home/data"))
ANURAN_VARIANT = os.environ.get("ANURAN_VARIANT", "public")

FAMILY_LEVELS = ["Bufonidae", "Dendrobatidae", "Hylidae", "Leptodactylidae"]
GENUS_LEVELS = [
    "Adenomera",
    "Ameerega",
    "Dendropsophus",
    "Hypsiboas",
    "Leptodactylus",
    "Osteocephalus",
    "Rhinella",
    "Scinax",
]
SPECIES_LEVELS = [
    "AdenomeraAndre",
    "AdenomeraHylaedactylus",
    "Ameeregatrivittata",
    "HylaMinuta",
    "HypsiboasCinerascens",
    "HypsiboasCordobae",
    "LeptodactylusFuscus",
    "OsteocephalusOophagus",
    "Rhinellagranulosa",
    "ScinaxRuber",
]
SAMPLED_ROW_IDS = list(range(0, 1500, 25))
TOL = 1e-5
AUDIT_KEYS = [
    "n_train_rows",
    "n_eval_rows",
    "n_train_records",
    "n_eval_records",
    "species_log_loss",
    "genus_log_loss",
    "family_log_loss",
    "species_brier",
    "genus_brier",
    "family_brier",
    "species_ece_10bin",
    "genus_ece_10bin",
    "family_ece_10bin",
    "family_residual_max",
    "genus_residual_max",
    "row_abstain_rate",
    "record_abstain_rate",
]


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    p = np.clip(np.asarray(p, dtype=float), 0, 1)
    y = np.asarray(y, dtype=float)
    idx = np.minimum((p * bins).astype(int), bins - 1)
    total = len(p)
    score = 0.0
    for b in range(bins):
        sel = idx == b
        if not np.any(sel):
            continue
        score += abs(float(p[sel].mean()) - float(y[sel].mean())) * sel.sum() / total
    return float(score)


def multiclass_brier(y: np.ndarray, probs: np.ndarray, levels: list[str]) -> float:
    y_idx = pd.Categorical(y, categories=levels, ordered=False).codes
    truth = np.zeros_like(probs)
    truth[np.arange(len(y_idx)), y_idx] = 1
    return float(np.mean(np.sum((probs - truth) ** 2, axis=1)))


def read_source() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "Frogs_MFCCs.csv")
    df.columns = [c.replace(" ", "") for c in df.columns]
    df = df.rename(columns={f"MFCCs_{i}": f"MFCC_{i}" for i in range(1, 23)})
    if "row_id" in df.columns:
        df["row_id"] = df["row_id"].astype(int)
    else:
        df["row_id"] = np.arange(len(df), dtype=int)
    return df


@pytest.fixture(scope="module")
def source():
    return read_source()


@pytest.fixture(scope="module")
def eval_truth(source):
    df = source[source["row_id"] % 5 == 0].copy()
    return df.sort_values("row_id").reset_index(drop=True)


@pytest.fixture(scope="module")
def predictions():
    return pd.read_csv(OUTPUT_DIR / "predictions.csv")


@pytest.fixture(scope="module")
def record_report():
    return pd.read_csv(OUTPUT_DIR / "record_report.csv")


@pytest.fixture(scope="module")
def audit():
    return json.loads((OUTPUT_DIR / "taxonomy_audit.json").read_text())


@pytest.fixture(scope="module")
def merged(predictions, eval_truth):
    return eval_truth.merge(predictions, on=["row_id", "RecordID"], how="inner", validate="one_to_one").sort_values("row_id").reset_index(drop=True)


def species_cols():
    return [f"prob_species_{nm}" for nm in SPECIES_LEVELS]


def genus_cols():
    return [f"prob_genus_{nm}" for nm in GENUS_LEVELS]


def family_cols():
    return [f"prob_family_{nm}" for nm in FAMILY_LEVELS]


def species_to_group_maps() -> tuple[dict[str, str], dict[str, str]]:
    genus_map = {
        "AdenomeraAndre": "Adenomera",
        "AdenomeraHylaedactylus": "Adenomera",
        "Ameeregatrivittata": "Ameerega",
        "HylaMinuta": "Dendropsophus",
        "HypsiboasCinerascens": "Hypsiboas",
        "HypsiboasCordobae": "Hypsiboas",
        "LeptodactylusFuscus": "Leptodactylus",
        "OsteocephalusOophagus": "Osteocephalus",
        "Rhinellagranulosa": "Rhinella",
        "ScinaxRuber": "Scinax",
    }
    family_map = {
        "AdenomeraAndre": "Leptodactylidae",
        "AdenomeraHylaedactylus": "Leptodactylidae",
        "Ameeregatrivittata": "Dendrobatidae",
        "HylaMinuta": "Hylidae",
        "HypsiboasCinerascens": "Hylidae",
        "HypsiboasCordobae": "Hylidae",
        "LeptodactylusFuscus": "Leptodactylidae",
        "OsteocephalusOophagus": "Hylidae",
        "Rhinellagranulosa": "Bufonidae",
        "ScinaxRuber": "Hylidae",
    }
    return genus_map, family_map


def row_metrics(df: pd.DataFrame, row_id: int):
    genus_map, family_map = species_to_group_maps()
    row = df[df["row_id"] == row_id].iloc[0]
    s = row[species_cols()].to_numpy(dtype=float)
    g = row[genus_cols()].to_numpy(dtype=float)
    f = row[family_cols()].to_numpy(dtype=float)
    return row, s, g, f, genus_map, family_map


def normalise_frame(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df[cols].copy()
    out = out.div(out.sum(axis=1), axis=0)
    return out


class TestPresence:
    def test_files_exist(self):
        """Required output files exist."""
        for name in ("predictions.csv", "record_report.csv", "taxonomy_audit.json"):
            assert (OUTPUT_DIR / name).exists(), f"missing {name}"

    def test_prediction_schema(self, predictions):
        """Prediction columns match the contract."""
        assert list(predictions.columns) == [
            "row_id",
            "RecordID",
            "pred_family",
            "pred_genus",
            "pred_species",
            "pred_abstain",
            *family_cols(),
            *genus_cols(),
            *species_cols(),
        ]

    def test_record_report_schema(self, record_report):
        """Record report columns match the contract."""
        assert list(record_report.columns) == [
            "RecordID",
            "n_rows",
            "obs_family",
            "obs_genus",
            "obs_species",
            "pred_family",
            "pred_genus",
            "pred_species",
            "record_abstain",
            "mean_pred_family_prob",
            "mean_pred_genus_prob",
            "mean_pred_species_prob",
        ]

    def test_audit_schema(self, audit):
        """Audit JSON exposes the complete flat metric schema."""
        assert set(audit) == set(AUDIT_KEYS)
        for key in AUDIT_KEYS:
            assert isinstance(audit[key], (int, float)) and not isinstance(audit[key], bool)
            assert math.isfinite(float(audit[key]))


class TestCoverage:
    def test_eval_rows(self, predictions, eval_truth, audit, source):
        """Predictions and metrics cover all evaluation rows."""
        assert len(predictions) == len(eval_truth) == int(audit["n_eval_rows"])
        assert int(audit["n_train_rows"]) == len(source) - len(eval_truth)

    def test_predictions_sorted_unique(self, predictions):
        """Prediction row identifiers are sorted and unique."""
        ids = predictions["row_id"].astype(int).tolist()
        assert ids == sorted(ids)
        assert len(ids) == len(set(ids))

    def test_eval_join_complete(self, predictions, eval_truth):
        """Predictions join one-to-one with the evaluation fold."""
        merged = eval_truth.merge(predictions, on=["row_id", "RecordID"], how="inner")
        assert len(merged) == len(eval_truth)

    def test_record_report_sorted_unique(self, record_report):
        """Record report is sorted and one row per evaluation record."""
        ids = record_report["RecordID"].astype(int).tolist()
        assert ids == sorted(ids)
        assert len(ids) == len(set(ids))


class TestPerRow:
    @pytest.mark.parametrize("row_id", SAMPLED_ROW_IDS)
    def test_row_contract(self, row_id, predictions, eval_truth):
        """Sampled rows satisfy the hierarchical probability contract."""
        pred = predictions[predictions["row_id"] == row_id].iloc[0]
        truth = eval_truth[eval_truth["row_id"] == row_id].iloc[0]
        _, s, g, f, genus_map, family_map = row_metrics(predictions, row_id)
        assert pred["RecordID"] == truth["RecordID"]
        assert pred["pred_species"] == SPECIES_LEVELS[int(np.argmax(s))]
        assert pred["pred_genus"] == GENUS_LEVELS[int(np.argmax(g))]
        assert pred["pred_family"] == FAMILY_LEVELS[int(np.argmax(f))]
        assert math.isfinite(float(s.sum())) and abs(float(s.sum()) - 1.0) <= TOL
        assert math.isfinite(float(g.sum())) and abs(float(g.sum()) - 1.0) <= TOL
        assert math.isfinite(float(f.sum())) and abs(float(f.sum()) - 1.0) <= TOL
        assert all(0.0 <= float(x) <= 1.0 for x in s)
        assert all(0.0 <= float(x) <= 1.0 for x in g)
        assert all(0.0 <= float(x) <= 1.0 for x in f)
        assert abs(float(pred[family_cols()].sum()) - 1.0) <= TOL
        assert abs(float(pred[genus_cols()].sum()) - 1.0) <= TOL
        species_family_sums = {}
        species_genus_sums = {}
        for sp, genus in genus_map.items():
            species_genus_sums.setdefault(genus, 0.0)
            species_genus_sums[genus] += float(pred[f"prob_species_{sp}"])
        for sp, family in family_map.items():
            species_family_sums.setdefault(family, 0.0)
            species_family_sums[family] += float(pred[f"prob_species_{sp}"])
        for family in FAMILY_LEVELS:
            assert abs(float(pred[f"prob_family_{family}"]) - float(species_family_sums[family])) <= TOL
        for genus in GENUS_LEVELS:
            assert abs(float(pred[f"prob_genus_{genus}"]) - float(species_genus_sums[genus])) <= TOL
        assert pred["pred_abstain"] in (0, 1)
        assert int(pred["pred_abstain"]) == int(max(s) < 0.55)


class TestMetricConsistency:
    def test_metrics_match(self, audit, merged):
        """Audit metrics match recomputation from predictions."""
        y_species = merged["Species"].astype(str).to_numpy()
        y_genus = merged["Genus"].astype(str).to_numpy()
        y_family = merged["Family"].astype(str).to_numpy()
        sprob = merged[species_cols()].to_numpy(dtype=float)
        gprob = merged[genus_cols()].to_numpy(dtype=float)
        fprob = merged[family_cols()].to_numpy(dtype=float)
        genus_map, family_map = species_to_group_maps()
        species_to_genus = np.zeros((len(SPECIES_LEVELS), len(GENUS_LEVELS)))
        species_to_family = np.zeros((len(SPECIES_LEVELS), len(FAMILY_LEVELS)))
        for i, sp_name in enumerate(SPECIES_LEVELS):
            species_to_genus[i, GENUS_LEVELS.index(genus_map[sp_name])] = 1
            species_to_family[i, FAMILY_LEVELS.index(family_map[sp_name])] = 1
        sprob_norm = normalise_frame(merged, species_cols()).to_numpy(dtype=float)
        gprob_norm = normalise_frame(merged, genus_cols()).to_numpy(dtype=float)
        fprob_norm = normalise_frame(merged, family_cols()).to_numpy(dtype=float)
        assert abs(float(audit["species_log_loss"]) - float(log_loss(y_species, sprob_norm, labels=SPECIES_LEVELS))) <= TOL
        assert abs(float(audit["genus_log_loss"]) - float(log_loss(y_genus, gprob_norm, labels=GENUS_LEVELS))) <= TOL
        assert abs(float(audit["family_log_loss"]) - float(log_loss(y_family, fprob_norm, labels=FAMILY_LEVELS))) <= TOL
        assert abs(float(audit["species_brier"]) - multiclass_brier(y_species, sprob, SPECIES_LEVELS)) <= TOL
        assert abs(float(audit["genus_brier"]) - multiclass_brier(y_genus, gprob, GENUS_LEVELS)) <= TOL
        assert abs(float(audit["family_brier"]) - multiclass_brier(y_family, fprob, FAMILY_LEVELS)) <= TOL
        assert abs(float(audit["species_ece_10bin"]) - ece(y_species == np.array(SPECIES_LEVELS)[np.argmax(sprob, axis=1)], np.max(sprob_norm, axis=1), 10)) <= TOL
        assert abs(float(audit["genus_ece_10bin"]) - ece(y_genus == np.array(GENUS_LEVELS)[np.argmax(gprob, axis=1)], np.max(gprob_norm, axis=1), 10)) <= TOL
        assert abs(float(audit["family_ece_10bin"]) - ece(y_family == np.array(FAMILY_LEVELS)[np.argmax(fprob, axis=1)], np.max(fprob_norm, axis=1), 10)) <= TOL
        assert abs(float(audit["family_residual_max"]) - float(np.max(np.abs(fprob - sprob @ species_to_family)))) <= TOL
        assert abs(float(audit["genus_residual_max"]) - float(np.max(np.abs(gprob - sprob @ species_to_genus)))) <= TOL
        assert abs(float(audit["row_abstain_rate"]) - float(merged["pred_abstain"].mean())) <= TOL

    def test_record_report_matches(self, record_report, merged):
        """Record-level aggregation matches recomputation."""
        for _, row in record_report.iterrows():
            part = merged[merged["RecordID"] == row["RecordID"]]
            assert int(row["n_rows"]) == len(part)
            assert row["obs_family"] == part["Family"].iloc[0]
            assert row["obs_genus"] == part["Genus"].iloc[0]
            assert row["obs_species"] == part["Species"].iloc[0]
            fam = part[family_cols()].mean(axis=0)
            gen = part[genus_cols()].mean(axis=0)
            sp = part[species_cols()].mean(axis=0)
            assert row["pred_family"] == fam.idxmax().replace("prob_family_", "")
            assert row["pred_genus"] == gen.idxmax().replace("prob_genus_", "")
            assert row["pred_species"] == sp.idxmax().replace("prob_species_", "")
            assert abs(float(row["mean_pred_family_prob"]) - float(fam.max())) <= TOL
            assert abs(float(row["mean_pred_genus_prob"]) - float(gen.max())) <= TOL
            assert abs(float(row["mean_pred_species_prob"]) - float(sp.max())) <= TOL
            assert int(row["record_abstain"]) == int(sp.max() < 0.55)

    def test_record_abstain_rate_matches(self, audit, record_report):
        """Audit record-abstain rate matches the record report."""
        assert abs(float(audit["record_abstain_rate"]) - float(record_report["record_abstain"].mean())) <= TOL


class TestBaselines:
    def test_candidate_beats_species_prior(self, audit, source, eval_truth, merged):
        """Candidate beats a naive species-prior baseline."""
        train = source[source["row_id"] % 5 != 0]
        prior = train["Species"].value_counts(normalize=True).reindex(SPECIES_LEVELS).fillna(0).to_numpy()
        baseline = np.tile(prior, (len(eval_truth), 1))
        assert float(audit["species_log_loss"]) < float(log_loss(eval_truth["Species"], baseline, labels=SPECIES_LEVELS))

    def test_candidate_beats_family_uniform_baseline(self, audit, source, eval_truth):
        """Candidate beats a family-uniform baseline."""
        train = source[source["row_id"] % 5 != 0]
        fam_prior = train["Family"].value_counts(normalize=True).reindex(FAMILY_LEVELS).fillna(0).to_numpy()
        family = np.tile(fam_prior, (len(eval_truth), 1))
        species = np.zeros((len(eval_truth), len(SPECIES_LEVELS)))
        for i, sp in enumerate(SPECIES_LEVELS):
            if sp.startswith("Adenomera"):
                fam = "Leptodactylidae"
            elif sp.startswith("Ameerega"):
                fam = "Dendrobatidae"
            elif sp.startswith(("Hyla", "Hypsiboas", "Osteocephalus", "Scinax")):
                fam = "Hylidae"
            else:
                fam = "Bufonidae"
            species[:, i] = family[:, FAMILY_LEVELS.index(fam)] / sum(
                1 for ss in SPECIES_LEVELS if (
                    (ss.startswith("Adenomera") and fam == "Leptodactylidae")
                    or (ss.startswith("Ameerega") and fam == "Dendrobatidae")
                    or (ss.startswith(("Hyla", "Hypsiboas", "Osteocephalus", "Scinax")) and fam == "Hylidae")
                    or (ss.startswith("Rhinella") and fam == "Bufonidae")
                )
            )
        species = species / species.sum(axis=1, keepdims=True)
        assert float(audit["species_log_loss"]) < float(log_loss(eval_truth["Species"], species, labels=SPECIES_LEVELS))

    def test_incoherent_head_baseline_is_incoherent(self, source, eval_truth):
        """Independent heads violate the nested-probability contract."""
        train = source[source["row_id"] % 5 != 0]
        sp = train["Species"].value_counts(normalize=True).reindex(SPECIES_LEVELS).fillna(0).to_numpy()
        fam = train["Family"].value_counts(normalize=True).reindex(FAMILY_LEVELS).fillna(0).to_numpy()
        gen = train["Genus"].value_counts(normalize=True).reindex(GENUS_LEVELS).fillna(0).to_numpy()
        species = np.tile(sp, (len(eval_truth), 1))
        genus = np.roll(np.tile(gen, (len(eval_truth), 1)), shift=1, axis=1)
        family = np.roll(np.tile(fam, (len(eval_truth), 1)), shift=1, axis=1)
        genus_map, family_map = species_to_group_maps()
        species_to_genus = np.zeros((len(SPECIES_LEVELS), len(GENUS_LEVELS)))
        species_to_family = np.zeros((len(SPECIES_LEVELS), len(FAMILY_LEVELS)))
        for i, sp_name in enumerate(SPECIES_LEVELS):
            species_to_genus[i, GENUS_LEVELS.index(genus_map[sp_name])] = 1
            species_to_family[i, FAMILY_LEVELS.index(family_map[sp_name])] = 1
        genus_from_species = species @ species_to_genus
        family_from_species = species @ species_to_family
        assert np.max(np.abs(genus - genus_from_species)) > 0.01
        assert np.max(np.abs(family - family_from_species)) > 0.01


class TestHiddenVariant:
    @pytest.mark.skipif(ANURAN_VARIANT == "public", reason="only runs on hidden variants")
    def test_hidden_eval_recordids_not_in_training(self, source):
        """Hidden variants prevent RecordID memorization across the split."""
        train_ids = set(source.loc[source["row_id"] % 5 != 0, "RecordID"].astype(int))
        eval_ids = set(source.loc[source["row_id"] % 5 == 0, "RecordID"].astype(int))
        assert train_ids.isdisjoint(eval_ids)

    @pytest.mark.skipif(ANURAN_VARIANT == "public", reason="only runs on hidden variants")
    def test_hidden_variant_metrics_finite(self, audit):
        """Hidden variant metrics stay finite."""
        for value in audit.values():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                assert math.isfinite(float(value))
