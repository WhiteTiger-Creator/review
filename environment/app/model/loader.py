"""
Model data loader module.
Loads prediction batches and ground truth labels from the data directory.
"""

import json
import os

import pandas as pd


def load_predictions(data_dir="/app/data/predictions"):
    """Load all prediction CSV batches from the predictions directory."""
    frames = []
    for fname in sorted(os.listdir(data_dir)):
        if fname.endswith(".csv"):
            df = pd.read_csv(os.path.join(data_dir, fname))
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    combined["prediction_date"] = pd.to_datetime(combined["prediction_date"])
    return combined


def load_ground_truth(path="/app/data/ground_truth/labels.json"):
    """Load ground truth class labels for all assets."""
    with open(path) as f:
        data = json.load(f)
    return {item["asset_id"]: item["true_class"] for item in data["assets"]}


def load_config(config_dir="/app/config"):
    """Load evaluation configuration parameters."""
    with open(os.path.join(config_dir, "eval_config.json")) as f:
        eval_cfg = json.load(f)
    with open(os.path.join(config_dir, "weights.json")) as f:
        weights_cfg = json.load(f)
    eval_cfg["class_weights"] = weights_cfg["class_weights"]
    return eval_cfg
