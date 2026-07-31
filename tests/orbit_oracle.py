"""Independent oracle for satellite conjunction covariance risk."""

from __future__ import annotations

import csv
import math
from datetime import datetime
from pathlib import Path

FIELDS_E = [
    "encounter_id",
    "primary_id",
    "secondary_id",
    "tca",
    "rx_km",
    "ry_km",
    "rz_km",
    "vx_km_s",
    "vy_km_s",
    "vz_km_s",
    "cxx",
    "cxy",
    "cxz",
    "cyy",
    "cyz",
    "czz",
    "quality_code",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})


def dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def norm(a: list[float]) -> float:
    return math.sqrt(dot(a, a))


def cross(a: list[float], b: list[float]) -> list[float]:
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def risk(row: dict[str, str], policy: dict[str, str]) -> tuple[float, float, float]:
    r = [float(row[k]) for k in ["rx_km", "ry_km", "rz_km"]]
    v = [float(row[k]) for k in ["vx_km_s", "vy_km_s", "vz_km_s"]]
    w = [x / norm(v) for x in v]
    ref = [1.0, 0.0, 0.0] if abs(w[0]) < 0.8 else [0.0, 1.0, 0.0]
    e1 = [ref[i] - dot(ref, w) * w[i] for i in range(3)]
    e1 = [x / norm(e1) for x in e1]
    e2 = cross(w, e1)
    scale = float(policy["covariance_scale"])
    hbr_km = float(policy["hard_body_radius_m"]) / 1000.0
    floor = float(policy["probability_floor"])
    cov = [
        [
            scale * float(row["cxx"]),
            scale * float(row["cxy"]),
            scale * float(row["cxz"]),
        ],
        [
            scale * float(row["cxy"]),
            scale * float(row["cyy"]),
            scale * float(row["cyz"]),
        ],
        [
            scale * float(row["cxz"]),
            scale * float(row["cyz"]),
            scale * float(row["czz"]),
        ],
    ]
    rp = [dot(e1, r), dot(e2, r)]
    cp00 = sum(e1[i] * cov[i][j] * e1[j] for i in range(3) for j in range(3))
    cp01 = sum(e1[i] * cov[i][j] * e2[j] for i in range(3) for j in range(3))
    cp11 = sum(e2[i] * cov[i][j] * e2[j] for i in range(3) for j in range(3))
    det = cp00 * cp11 - cp01 * cp01
    miss = norm(rp)
    if det <= 0:
        base = 1.0 if miss == 0 else 0.0
        return miss, 0.0 if miss == 0 else float("inf"), min(1.0, base + floor)
    inv00, inv01, inv11 = cp11 / det, -cp01 / det, cp00 / det
    q = rp[0] * (inv00 * rp[0] + inv01 * rp[1]) + rp[1] * (
        inv01 * rp[0] + inv11 * rp[1]
    )
    sig = math.sqrt(max(q, 0.0))
    radial_nodes = [0.1127016654, 0.5, 0.8872983346]
    radial_weights = [5.0 / 18.0, 8.0 / 18.0, 5.0 / 18.0]
    angle_weight = 2.0 * math.pi / 12.0
    disk_mass = 0.0
    for radius_node, radius_weight in zip(radial_nodes, radial_weights):
        for step in range(12):
            theta = angle_weight * step
            point = [
                hbr_km * radius_node * math.cos(theta),
                hbr_km * radius_node * math.sin(theta),
            ]
            dx = point[0] - rp[0]
            dy = point[1] - rp[1]
            q_point = dx * (inv00 * dx + inv01 * dy) + dy * (inv01 * dx + inv11 * dy)
            density = math.exp(-0.5 * max(q_point, 0.0)) / (
                2.0 * math.pi * math.sqrt(det)
            )
            disk_mass += (
                radius_weight
                * angle_weight
                * hbr_km
                * hbr_km
                * radius_node
                * density
            )
    prob = min(1.0, disk_mass + floor)
    return miss, sig, prob


def s6(x: float) -> str:
    return f"{round(x + 0.0, 6):.6f}"


def policy_probability_threshold(encounter_tca: str, policy: dict[str, str]) -> float:
    age_hours = (
        datetime.fromisoformat(encounter_tca)
        - datetime.fromisoformat(policy["effective_tca"])
    ).total_seconds() / 3600.0
    age_factor = 1.0 + min(0.25, 0.015 * math.floor(age_hours / 6.0))
    return float(policy["max_probability"]) * age_factor


def generate(root: Path, seed: int) -> None:
    rows = []
    sats = ["SAT-A", "SAT-B", "SAT-C", "SAT-D"]
    for i in range(16):
        q = "HIGH" if i % 3 else "LOW"
        rows.append(
            {
                "encounter_id": f"H{seed:02d}{i:03d}",
                "primary_id": sats[i % len(sats)],
                "secondary_id": f"OBJ-{seed}-{i}",
                "tca": f"2026-06-{1 + i // 4:02d}T{(i * 3) % 24:02d}:00",
                "rx_km": round(0.15 + ((seed + i * 7) % 18) / 10, 3),
                "ry_km": round(((seed * 2 + i * 5) % 11) / 10, 3),
                "rz_km": round(((seed + i) % 5) / 10, 3),
                "vx_km_s": round(0.05 * ((i % 5) + 1), 3),
                "vy_km_s": round(7.0 + ((seed + i) % 7) / 10, 3),
                "vz_km_s": round(0.1 + (i % 4) / 10, 3),
                "cxx": round(0.35 + (i % 5) * 0.2, 3),
                "cxy": round(0.01 * (i % 3), 3),
                "cxz": round(0.005 * (i % 2), 3),
                "cyy": round(0.32 + ((i + seed) % 6) * 0.18, 3),
                "cyz": round(0.006 * (i % 4), 3),
                "czz": round(0.4 + (i % 4) * 0.16, 3),
                "quality_code": q,
            }
        )
    policies = [
        {
            "policy_id": "P1",
            "effective_tca": "2026-05-01T00:00",
            "revision_ts": "2026-04-25T09:00",
            "status": "approved",
            "quality_code": "HIGH",
            "max_miss_km": 1.1,
            "max_sigma_distance": 1.8,
            "max_probability": 0.000012,
            "covariance_scale": 1.00,
            "hard_body_radius_m": 9.0,
            "probability_floor": 0.000000,
        },
        {
            "policy_id": "P2",
            "effective_tca": "2026-05-01T00:00",
            "revision_ts": "2026-04-25T09:00",
            "status": "approved",
            "quality_code": "LOW",
            "max_miss_km": 0.8,
            "max_sigma_distance": 1.3,
            "max_probability": 0.000015,
            "covariance_scale": 0.90,
            "hard_body_radius_m": 12.0,
            "probability_floor": 0.000001,
        },
        {
            "policy_id": "P3",
            "effective_tca": "2026-06-03T00:00",
            "revision_ts": "2026-06-02T08:00",
            "status": "draft",
            "quality_code": "HIGH",
            "max_miss_km": 9.0,
            "max_sigma_distance": 9.0,
            "max_probability": 0.000001,
            "covariance_scale": 3.00,
            "hard_body_radius_m": 55.0,
            "probability_floor": 0.250000,
        },
        {
            "policy_id": "P4",
            "effective_tca": "2026-06-03T00:00",
            "revision_ts": "2026-06-02T10:00",
            "status": "approved",
            "quality_code": "HIGH",
            "max_miss_km": 1.0,
            "max_sigma_distance": 1.6,
            "max_probability": 0.000018,
            "covariance_scale": 1.20,
            "hard_body_radius_m": 16.0,
            "probability_floor": 0.000002,
        },
        {
            "policy_id": "P5",
            "effective_tca": "2026-06-03T00:00",
            "revision_ts": "2026-06-02T13:00",
            "status": "approved",
            "quality_code": "HIGH",
            "max_miss_km": 0.95,
            "max_sigma_distance": 1.55,
            "max_probability": 0.000020,
            "covariance_scale": 0.72,
            "hard_body_radius_m": 21.0,
            "probability_floor": 0.000003,
        },
    ]
    blackouts = [
        {
            "primary_id": "SAT-B",
            "start_tca": "2026-06-02T00:00",
            "end_tca": "2026-06-03T12:00",
            "status": "approved",
        }
    ]
    write_csv(root / "orbits/encounters.csv", rows, FIELDS_E)
    write_csv(
        root / "policy/screening_policies.csv",
        policies,
        [
            "policy_id",
            "effective_tca",
            "revision_ts",
            "status",
            "quality_code",
            "max_miss_km",
            "max_sigma_distance",
            "max_probability",
            "covariance_scale",
            "hard_body_radius_m",
            "probability_floor",
        ],
    )
    write_csv(
        root / "policy/maneuver_blackouts.csv",
        blackouts,
        ["primary_id", "start_tca", "end_tca", "status"],
    )


def expected(root: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], int]:
    encounters = read_csv(root / "orbits/encounters.csv")
    policies = read_csv(root / "policy/screening_policies.csv")
    blackouts = read_csv(root / "policy/maneuver_blackouts.csv")
    out = []
    cases = 0
    for e in encounters:
        active = [
            p
            for p in policies
            if p["status"] == "approved"
            and p["quality_code"] == e["quality_code"]
            and p["effective_tca"] <= e["tca"]
        ]
        p = max(
            active, key=lambda x: (x["effective_tca"], x["revision_ts"], x["policy_id"])
        )
        blackout = any(
            b["status"] == "approved"
            and b["primary_id"] == e["primary_id"]
            and b["start_tca"] <= e["tca"] < b["end_tca"]
            for b in blackouts
        )
        miss, sig, prob = risk(e, p)
        breach = (
            (not blackout)
            and miss <= float(p["max_miss_km"])
            and sig <= float(p["max_sigma_distance"])
            and prob >= policy_probability_threshold(e["tca"], p)
        )
        out.append(
            {
                "encounter_id": e["encounter_id"],
                "primary_id": e["primary_id"],
                "secondary_id": e["secondary_id"],
                "projected_miss_km": s6(miss),
                "sigma_distance": s6(sig),
                "probability": s6(prob),
                "blackout": "TRUE" if blackout else "FALSE",
                "decision": "BREACH" if breach else "CLEAR",
            }
        )
        cases += 7
    summ = []
    for pid in sorted({r["primary_id"] for r in out}):
        part = [r for r in out if r["primary_id"] == pid]
        summ.append(
            {
                "primary_id": pid,
                "total_encounters": str(len(part)),
                "breaches": str(sum(r["decision"] == "BREACH" for r in part)),
                "blackout_suppressed": str(sum(r["blackout"] == "TRUE" for r in part)),
                "max_probability": s6(max(float(r["probability"]) for r in part)),
                "min_projected_miss_km": s6(
                    min(float(r["projected_miss_km"]) for r in part)
                ),
            }
        )
        cases += 4
    return out, summ, cases
