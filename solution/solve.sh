#!/bin/bash
set -euo pipefail
cd /app

python3 << 'PYEOF'
import json

# Correction 1: Temporal split direction (preprocessor.py)
# Protocol R1: keep predictions >= cutoff, not < cutoff
path = "/app/model/preprocessor.py"
with open(path) as f:
    src = f.read()

old = '    return df[df["prediction_date"] < cutoff].copy()'
new = '    return df[df["prediction_date"] >= cutoff].copy()'
assert old in src, f"Correction 1 target not found"
src = src.replace(old, new, 1)
with open(path, "w") as f:
    f.write(src)

# Correction 2: Dedup keeps latest (preprocessor.py)
# Protocol R2: keep='last' after date sort
path = "/app/model/preprocessor.py"
with open(path) as f:
    src = f.read()

old = '    return df_sorted.drop_duplicates(subset="asset_id", keep="first")'
new = '    return df_sorted.drop_duplicates(subset="asset_id", keep="last")'
assert old in src, f"Correction 2 target not found"
src = src.replace(old, new, 1)
with open(path, "w") as f:
    f.write(src)

# Correction 3: Calibration divides by temperature (calibration.py)
# Protocol R4: calibrated = confidence / temperature
path = "/app/eval/calibration.py"
with open(path) as f:
    src = f.read()

old = '    calibrated = confidence_scores * temperature'
new = '    calibrated = confidence_scores / temperature'
assert old in src, f"Correction 3 target not found"
src = src.replace(old, new, 1)
with open(path, "w") as f:
    f.write(src)

# Correction 4 & 6: Fleet score - penalty after norm + multiplicative weights (metrics.py)
path = "/app/eval/metrics.py"
with open(path) as f:
    src = f.read()

old = """        # Apply penalty for false-critical (predicted critical, actual operational)
        if pred == "critical" and actual == "operational":
            score = score * penalty_mult

        # Normalize score to [0, 1] range
        score = max(0.0, min(1.0, score))

        scores.append(score * cw + priority_weight)
        weights.append(cw + priority_weight)"""
new = """        # Normalize score to [0, 1] range first
        score = max(0.0, min(1.0, score))

        # Apply penalty for false-critical AFTER normalization
        if pred == "critical" and actual == "operational":
            score = score * penalty_mult
            score = max(0.0, min(1.0, score))

        # Multiplicative weight combination per protocol R13
        scores.append(score * cw * priority_weight)
        weights.append(cw * priority_weight)"""
assert old in src, f"Correction 4/6 target not found"
src = src.replace(old, new, 1)

# Correction 5: Temporal decay with ln(2) (metrics.py)
old = '    return np.exp(-ages_days / half_life)'
new = '    return np.exp(-np.log(2) * ages_days / half_life)'
assert old in src, f"Correction 5 target not found"
src = src.replace(old, new, 1)

with open(path, "w") as f:
    f.write(src)

# Correction 7: Class weights (weights.json)
path = "/app/config/weights.json"
correct_weights = {
    "class_weights": {
        "operational": 0.4,
        "degraded": 0.3,
        "critical": 0.2,
        "offline": 0.1
    },
    "_reference": "Fleet Readiness Evaluation Protocol v3.2 Rule R16"
}
with open(path, "w") as f:
    json.dump(correct_weights, f, indent=4)

# Correction 8: Min predictions threshold (eval_config.json)
path = "/app/config/eval_config.json"
with open(path) as f:
    cfg = json.load(f)
cfg["min_predictions"] = 3
with open(path, "w") as f:
    json.dump(cfg, f, indent=4)

print("All 8 corrections applied successfully.")
PYEOF

# Run evaluation with corrected pipeline
python3 /app/run_evaluation.py
