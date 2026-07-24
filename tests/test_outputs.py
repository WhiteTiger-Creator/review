import csv
import hashlib
import json
import math
import os
import random
import shutil
import subprocess
import tempfile
import unittest
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path("/app/task_file")
EXE = ROOT / "sphere-flux.exe"
TASK_UID = 10001
REPORTS = [
    "cell_flux.csv",
    "ring_summary.csv",
    "mode_coupling.csv",
    "region_balance.json",
    "gradient_audit.csv",
    "latitude_frontier.csv",
    "mode_spectrum.csv",
    "ring_mode_breakdown.csv",
]
PUBLIC_HASHES = {
    "settings.csv": "7ee1932f27b1243d10dfebe469a9ba7ba742f35b091c1e94ef4e6bee6aba8dac",
    "rings.csv": "d1af7d5d0ea55b45eb8a227f9ce4c32cfd3b576f5e0171d6b781ddc765087457",
    "cells.csv": "973bb91fa7a48d7a19f4ed7e6d36c5e6b71795a552c7a70b7178dae4bdf7771f",
    "modes.csv": "040206502913feac58bc77c1abbdde66ed600de248e14bba46b9519203f30a98",
}


def f6(value: float) -> str:
    quant = Decimal("0.000001")
    rounded = Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP)
    if abs(rounded) < Decimal("0.0000005"):
        rounded = Decimal(0)
    return f"{rounded:.6f}"


def read_csv(path: Path, header):
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    if not rows or rows[0] != header:
        raise ValueError(f"bad header for {path}")
    if any(len(row) != len(header) for row in rows[1:]):
        raise ValueError(f"bad row for {path}")
    return rows[1:]


def token(value: str) -> str:
    if not value or any(ch in value for ch in ',\n\r"'):
        raise ValueError("bad token")
    return value


def norm_phi(start: float, end: float):
    width = end - start
    if width <= 0 or width > 360:
        raise ValueError("bad phi width")
    if width == 360:
        return [(0.0, 2.0 * math.pi)]
    s = start % 360.0
    e = s + width
    if e <= 360.0:
        return [(math.radians(s), math.radians(e))]
    return [(math.radians(s), 2.0 * math.pi), (0.0, math.radians(e - 360.0))]


def gauss_legendre(n: int):
    xs = [0.0] * n
    ws = [0.0] * n
    m = (n + 1) // 2
    for i in range(m):
        z = math.cos(math.pi * (i + 0.75) / (n + 0.5))
        while True:
            p1 = 1.0
            p2 = 0.0
            for j in range(1, n + 1):
                p3 = p2
                p2 = p1
                p1 = ((2.0 * j - 1.0) * z * p2 - (j - 1.0) * p3) / j
            pp = n * (z * p1 - p2) / (z * z - 1.0)
            z1 = z
            z = z1 - p1 / pp
            if abs(z - z1) <= 1e-15:
                break
        xs[i] = -z
        xs[n - 1 - i] = z
        weight = 2.0 / ((1.0 - z * z) * pp * pp)
        ws[i] = weight
        ws[n - 1 - i] = weight
    return xs, ws


def assoc_legendre(ell: int, m: int, x: float) -> float:
    pmm = 1.0
    if m:
        somx2 = math.sqrt(max(0.0, (1.0 - x) * (1.0 + x)))
        fact = 1.0
        for _ in range(1, m + 1):
            pmm *= -fact * somx2
            fact += 2.0
    if ell == m:
        return pmm
    pmmp1 = x * (2.0 * m + 1.0) * pmm
    if ell == m + 1:
        return pmmp1
    plm2 = pmm
    plm1 = pmmp1
    pll = 0.0
    for lval in range(m + 2, ell + 1):
        pll = ((2.0 * lval - 1.0) * x * plm1 - (lval + m - 1.0) * plm2) / (lval - m)
        plm2 = plm1
        plm1 = pll
    return pll


def assoc_legendre_derivative(ell: int, m: int, x: float, pell: float) -> float:
    prev = 0.0 if ell == m else assoc_legendre(ell - 1, m, x)
    return (ell * x * pell - (ell + m) * prev) / (x * x - 1.0)


def parse_case(input_dir: Path):
    settings_rows = read_csv(input_dir / "settings.csv", ["key", "value"])
    settings = {}
    for key, value in settings_rows:
        if key in settings:
            raise ValueError("duplicate setting")
        settings[key] = value
    required = {"quadrature_order", "rotation_degrees", "clip_floor", "alert_flux"}
    if set(settings) != required:
        raise ValueError("bad settings")
    q = int(settings["quadrature_order"])
    if not 4 <= q <= 24:
        raise ValueError("bad q")
    parsed_settings = {
        "quadrature_order": q,
        "rotation": math.radians(finite_float(settings["rotation_degrees"])),
        "clip_floor": finite_float(settings["clip_floor"]),
        "alert_flux": finite_float(settings["alert_flux"]),
    }

    rings = []
    ring_by_id = {}
    for order, row in enumerate(read_csv(input_dir / "rings.csv", ["ring_id", "theta_min_deg", "theta_max_deg"])):
        rid = token(row[0])
        if rid in ring_by_id:
            raise ValueError("duplicate ring")
        t0 = finite_float(row[1])
        t1 = finite_float(row[2])
        if not (0.0 <= t0 < t1 <= 180.0):
            raise ValueError("bad theta")
        ring = {"id": rid, "theta_min": t0, "theta_max": t1, "order": order}
        rings.append(ring)
        ring_by_id[rid] = ring

    cells = []
    seen_cells = set()
    for order, row in enumerate(read_csv(input_dir / "cells.csv", ["cell_id", "ring_id", "phi_start_deg", "phi_end_deg", "region", "exposure"])):
        cid = token(row[0])
        rid = token(row[1])
        region = token(row[4])
        if cid in seen_cells or rid not in ring_by_id:
            raise ValueError("bad cell id")
        seen_cells.add(cid)
        start = finite_float(row[2])
        end = finite_float(row[3])
        exposure = finite_float(row[5])
        if not exposure > 0.0:
            raise ValueError("bad exposure")
        cell = {
            "id": cid,
            "ring": ring_by_id[rid],
            "region": region,
            "phi_start": start,
            "phi_end": end,
            "exposure": exposure,
            "order": order,
            "segments": norm_phi(start, end),
        }
        cells.append(cell)

    modes = []
    seen_modes = set()
    for order, row in enumerate(read_csv(input_dir / "modes.csv", ["mode_id", "ell", "m", "kind", "coefficient"])):
        mid = token(row[0])
        if mid in seen_modes:
            raise ValueError("duplicate mode")
        seen_modes.add(mid)
        ell = int(row[1])
        m = int(row[2])
        kind = row[3]
        if kind not in {"C", "S"} or ell < 0 or m < 0 or m > ell or (kind == "S" and m == 0):
            raise ValueError("bad mode")
        modes.append({"id": mid, "ell": ell, "m": m, "kind": kind, "coeff": finite_float(row[4]), "order": order})
    if not rings or not cells or not modes:
        raise ValueError("missing primary rows")
    nodes, weights = gauss_legendre(q)
    return parsed_settings, rings, cells, modes, nodes, weights


def finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("bad finite number")
    return value


def zero_cell_result(cell, mode_count):
    return {
        "cell": cell,
        "area": 0.0,
        "raw": 0.0,
        "clipped": 0.0,
        "mean_raw": 0.0,
        "mean_clipped": 0.0,
        "clipped_nodes": 0,
        "mode_contrib": [0.0] * mode_count,
        "theta_energy": 0.0,
        "phi_energy": 0.0,
        "gradient_mode": [0.0] * mode_count,
        "coupling": [[0.0] * mode_count for _ in range(mode_count)],
        "weighted": [[0.0] * mode_count for _ in range(mode_count)],
    }


def integrate_cell(settings, cell, modes, nodes, weights, theta_min, theta_max, include_mode_audits=True):
    result = zero_cell_result(cell, len(modes))
    if not theta_max > theta_min:
        return result
    mu_a = math.cos(math.radians(theta_max))
    mu_b = math.cos(math.radians(theta_min))
    mu_mid = 0.5 * (mu_a + mu_b)
    mu_half = 0.5 * (mu_b - mu_a)
    for phi_a, phi_b in cell["segments"]:
        phi_mid = 0.5 * (phi_a + phi_b)
        phi_half = 0.5 * (phi_b - phi_a)
        for node_mu, weight_mu0 in zip(nodes, weights):
            mu = mu_mid + mu_half * node_mu
            weight_mu = mu_half * weight_mu0
            for node_phi, weight_phi0 in zip(nodes, weights):
                phi = phi_mid + phi_half * node_phi
                weight = weight_mu * phi_half * weight_phi0
                phi_eval = phi + settings["rotation"]
                basis = []
                dmu_basis = []
                dphi_basis = []
                field = 0.0
                field_mu = 0.0
                field_phi = 0.0
                for mode in modes:
                    pval = assoc_legendre(mode["ell"], mode["m"], mu)
                    cos_v = math.cos(mode["m"] * phi_eval)
                    sin_v = math.sin(mode["m"] * phi_eval)
                    trig = cos_v if mode["kind"] == "C" else sin_v
                    dtrig = -mode["m"] * sin_v if mode["kind"] == "C" else mode["m"] * cos_v
                    dp = assoc_legendre_derivative(mode["ell"], mode["m"], mu, pval)
                    bval = pval * trig
                    dmuv = dp * trig
                    dphiv = pval * dtrig
                    basis.append(bval)
                    dmu_basis.append(dmuv)
                    dphi_basis.append(dphiv)
                    field += mode["coeff"] * bval
                    field_mu += mode["coeff"] * dmuv
                    field_phi += mode["coeff"] * dphiv
                result["area"] += weight
                result["raw"] += cell["exposure"] * field * weight
                result["clipped"] += cell["exposure"] * max(field, settings["clip_floor"]) * weight
                if field < settings["clip_floor"]:
                    result["clipped_nodes"] += 1
                for i, mode in enumerate(modes):
                    result["mode_contrib"][i] += cell["exposure"] * mode["coeff"] * basis[i] * weight
                one_minus = max(0.0, 1.0 - mu * mu)
                theta_energy = one_minus * field_mu * field_mu
                phi_energy = 0.0 if one_minus == 0.0 else field_phi * field_phi / one_minus
                result["theta_energy"] += cell["exposure"] * theta_energy * weight
                result["phi_energy"] += cell["exposure"] * phi_energy * weight
                for i, mode in enumerate(modes):
                    mode_mu = mode["coeff"] * dmu_basis[i]
                    mode_phi = mode["coeff"] * dphi_basis[i]
                    self_energy = one_minus * mode_mu * mode_mu + (0.0 if one_minus == 0.0 else mode_phi * mode_phi / one_minus)
                    result["gradient_mode"][i] += cell["exposure"] * self_energy * weight
                if include_mode_audits:
                    for i in range(len(modes)):
                        for j in range(len(modes)):
                            v = basis[i] * basis[j] * weight
                            result["coupling"][i][j] += v
                            result["weighted"][i][j] += cell["exposure"] * v
    denom = cell["exposure"] * result["area"]
    if denom:
        result["mean_raw"] = result["raw"] / denom
        result["mean_clipped"] = result["clipped"] / denom
    return result


def dominant_mode(modes, contrib):
    best = 0
    best_abs = abs(contrib[0])
    for idx in range(1, len(contrib)):
        cand = abs(contrib[idx])
        if cand > best_abs:
            best_abs = cand
            best = idx
    return modes[best]["id"]


def add_region(accum, result):
    accum["cell_count"] += 1
    accum["area"] += result["area"]
    accum["raw"] += result["raw"]
    accum["clipped"] += result["clipped"]
    for i in range(len(accum["mode_contrib"])):
        accum["mode_contrib"][i] += result["mode_contrib"][i]
        for j in range(len(accum["mode_contrib"])):
            accum["coupling"][i][j] += result["coupling"][i][j]
            accum["weighted"][i][j] += result["weighted"][i][j]


def render_expected(input_dir: Path):
    settings, rings, cells, modes, nodes, weights = parse_case(input_dir)
    cell_results = [
        integrate_cell(settings, cell, modes, nodes, weights, cell["ring"]["theta_min"], cell["ring"]["theta_max"])
        for cell in cells
    ]
    regions = {}
    for result in cell_results:
        region = result["cell"]["region"]
        if region not in regions:
            n = len(modes)
            regions[region] = {
                "cell_count": 0,
                "area": 0.0,
                "raw": 0.0,
                "clipped": 0.0,
                "mode_contrib": [0.0] * n,
                "coupling": [[0.0] * n for _ in range(n)],
                "weighted": [[0.0] * n for _ in range(n)],
            }
        add_region(regions[region], result)

    out = {}
    lines = ["cell_id,ring_id,region,area,raw_flux,clipped_flux,mean_raw,mean_clipped,clipped_nodes,dominant_mode"]
    for result in sorted(cell_results, key=lambda r: r["cell"]["order"]):
        cell = result["cell"]
        lines.append(",".join([
            cell["id"], cell["ring"]["id"], cell["region"], f6(result["area"]), f6(result["raw"]),
            f6(result["clipped"]), f6(result["mean_raw"]), f6(result["mean_clipped"]),
            str(result["clipped_nodes"]), dominant_mode(modes, result["mode_contrib"]),
        ]))
    out["cell_flux.csv"] = "\n".join(lines) + "\n"

    lines = ["ring_id,cell_count,total_area,total_raw_flux,total_clipped_flux,clip_delta,max_mean_cell,alert_count,regions"]
    by_ring = defaultdict(list)
    for result in cell_results:
        by_ring[result["cell"]["ring"]["id"]].append(result)
    for ring in sorted(rings, key=lambda r: r["order"]):
        group = sorted(by_ring[ring["id"]], key=lambda r: r["cell"]["order"])
        area = sum(r["area"] for r in group)
        raw = sum(r["raw"] for r in group)
        clipped = sum(r["clipped"] for r in group)
        max_cell = ""
        if group:
            max_cell = max(group, key=lambda r: (r["mean_clipped"], -r["cell"]["order"]))["cell"]["id"]
        alert_count = sum(1 for r in group if r["clipped"] >= settings["alert_flux"])
        counts = defaultdict(int)
        for r in group:
            counts[r["cell"]["region"]] += 1
        region_text = ";".join(f"{name}:{counts[name]}" for name in sorted(counts))
        lines.append(",".join([
            ring["id"], str(len(group)), f6(area), f6(raw), f6(clipped), f6(clipped - raw),
            max_cell, str(alert_count), region_text,
        ]))
    out["ring_summary.csv"] = "\n".join(lines) + "\n"

    lines = ["region,mode_a,mode_b,coupling,weighted_coupling,correlation"]
    for region in sorted(regions):
        accum = regions[region]
        for i, mode_a in enumerate(modes):
            for j in range(i, len(modes)):
                denom = math.sqrt(abs(accum["weighted"][i][i] * accum["weighted"][j][j]))
                corr = 0.0 if denom == 0.0 else accum["weighted"][i][j] / denom
                lines.append(",".join([
                    region, mode_a["id"], modes[j]["id"], f6(accum["coupling"][i][j]),
                    f6(accum["weighted"][i][j]), f6(corr),
                ]))
    out["mode_coupling.csv"] = "\n".join(lines) + "\n"

    total_area = sum(accum["area"] for accum in regions.values())
    total_raw = sum(accum["raw"] for accum in regions.values())
    total_clipped = sum(accum["clipped"] for accum in regions.values())
    region_parts = []
    for region in sorted(regions):
        accum = regions[region]
        escaped_region = region.replace("\\", "\\\\").replace('"', '\\"')
        region_parts.append(
            (
                '{{"region":"{}","cell_count":{},"area":{},"raw_flux":{},"clipped_flux":{},'
                '"clip_delta":{},"dominant_mode":"{}"}}'
            ).format(
                escaped_region,
                accum["cell_count"],
                f6(accum["area"]),
                f6(accum["raw"]),
                f6(accum["clipped"]),
                f6(accum["clipped"] - accum["raw"]),
                dominant_mode(modes, accum["mode_contrib"]),
            )
        )
    out["region_balance.json"] = (
        '{{"total_area":{},"total_raw_flux":{},"total_clipped_flux":{},"clip_delta":{},"regions":[{}]}}\n'.format(
            f6(total_area),
            f6(total_raw),
            f6(total_clipped),
            f6(total_clipped - total_raw),
            ",".join(region_parts),
        )
    )

    lines = ["cell_id,region,theta_energy,phi_energy,total_gradient_energy,anisotropy,dominant_gradient_mode"]
    for result in sorted(cell_results, key=lambda r: r["cell"]["order"]):
        total_gradient = result["theta_energy"] + result["phi_energy"]
        anisotropy = 0.0 if total_gradient == 0.0 else result["phi_energy"] / total_gradient
        lines.append(",".join([
            result["cell"]["id"],
            result["cell"]["region"],
            f6(result["theta_energy"]),
            f6(result["phi_energy"]),
            f6(total_gradient),
            f6(anisotropy),
            dominant_mode(modes, result["gradient_mode"]),
        ]))
    out["gradient_audit.csv"] = "\n".join(lines) + "\n"

    faces = sorted({ring["theta_min"] for ring in rings} | {ring["theta_max"] for ring in rings})
    lines = ["face,theta_deg,area_left,raw_flux_left,clipped_flux_left,clip_delta_left,active_cells"]
    for face, theta in enumerate(faces):
        area = raw = clipped = 0.0
        active = 0
        for cell in cells:
            a = cell["ring"]["theta_min"]
            b = min(theta, cell["ring"]["theta_max"])
            if b > a:
                active += 1
                part = integrate_cell(settings, cell, modes, nodes, weights, a, b, include_mode_audits=False)
                area += part["area"]
                raw += part["raw"]
                clipped += part["clipped"]
        lines.append(",".join([str(face), f6(theta), f6(area), f6(raw), f6(clipped), f6(clipped - raw), str(active)]))
    out["latitude_frontier.csv"] = "\n".join(lines) + "\n"

    mode_gradient_totals = [sum(result["gradient_mode"][idx] for result in cell_results) for idx in range(len(modes))]
    all_mode_gradient = sum(mode_gradient_totals)
    lines = ["mode_id,total_raw_contribution,positive_cells,negative_cells,dominant_cell,gradient_energy,gradient_share"]
    for idx, mode in enumerate(modes):
        per_cell = [result["mode_contrib"][idx] for result in cell_results]
        dominant = max(cell_results, key=lambda result: (abs(result["mode_contrib"][idx]), -result["cell"]["order"]))["cell"]["id"]
        share = 0.0 if all_mode_gradient == 0.0 else mode_gradient_totals[idx] / all_mode_gradient
        lines.append(",".join([
            mode["id"],
            f6(sum(per_cell)),
            str(sum(1 for value in per_cell if value > 0.0)),
            str(sum(1 for value in per_cell if value < 0.0)),
            dominant,
            f6(mode_gradient_totals[idx]),
            f6(share),
        ]))
    out["mode_spectrum.csv"] = "\n".join(lines) + "\n"

    lines = ["ring_id,mode_id,raw_contribution,share_of_ring_raw,gradient_energy,dominant_region"]
    for ring in sorted(rings, key=lambda r: r["order"]):
        group = [result for result in cell_results if result["cell"]["ring"]["id"] == ring["id"]]
        ring_raw = sum(result["raw"] for result in group)
        for idx, mode in enumerate(modes):
            raw = sum(result["mode_contrib"][idx] for result in group)
            gradient = sum(result["gradient_mode"][idx] for result in group)
            by_region = defaultdict(float)
            for result in group:
                by_region[result["cell"]["region"]] += result["mode_contrib"][idx]
            dominant_region = ""
            if by_region:
                dominant_region = min(by_region, key=lambda region: (-abs(by_region[region]), region))
            share = 0.0 if ring_raw == 0.0 else raw / ring_raw
            lines.append(",".join([
                ring["id"],
                mode["id"],
                f6(raw),
                f6(share),
                f6(gradient),
                dominant_region,
            ]))
    out["ring_mode_breakdown.csv"] = "\n".join(lines) + "\n"
    return out


def chmod_tree(path: Path):
    for item in [path] + list(path.rglob("*")):
        if item.is_dir():
            os.chmod(item, 0o755)
        else:
            os.chmod(item, 0o644)


def run_tool(input_dir: Path, output_dir: Path, no_args=False):
    if no_args:
        cmd = ["setpriv", f"--reuid={TASK_UID}", f"--regid={TASK_UID}", "--clear-groups", "mono", str(EXE)]
    else:
        cmd = [
            "setpriv", f"--reuid={TASK_UID}", f"--regid={TASK_UID}", "--clear-groups",
            "mono", str(EXE), str(input_dir), str(output_dir),
        ]
    return subprocess.run(cmd, cwd="/tmp", capture_output=True, text=True, timeout=60, check=False)


def read_outputs(output_dir: Path):
    actual_files = {path.name for path in output_dir.iterdir() if path.is_file()}
    assert actual_files == set(REPORTS), actual_files
    actual = {}
    for report in REPORTS:
        data = (output_dir / report).read_text(encoding="utf-8")
        assert data.endswith("\n")
        assert not data.endswith("\n\n")
        actual[report] = data
    return actual


def assert_outputs_match(testcase: unittest.TestCase, input_dir: Path, output_dir: Path):
    expected = render_expected(input_dir)
    actual = read_outputs(output_dir)
    testcase.assertEqual(actual, expected)
    parsed_json = json.loads(actual["region_balance.json"])
    testcase.assertEqual(list(parsed_json.keys()), ["total_area", "total_raw_flux", "total_clipped_flux", "clip_delta", "regions"])


def write_case(root: Path, files: dict[str, str]):
    root.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (root / name).write_text(content, encoding="utf-8")
    chmod_tree(root)


def generated_case(seed: int, hard: bool = False):
    rng = random.Random(seed)
    q = rng.choice([6, 8, 10, 12]) if not hard else rng.choice([9, 11, 13])
    settings = [
        "key,value",
        f"quadrature_order,{q}",
        f"rotation_degrees,{rng.uniform(-35, 55):.8f}",
        f"clip_floor,{rng.uniform(-0.35, 0.05):.8f}",
        f"alert_flux,{rng.uniform(0.015, 0.18):.8f}",
    ]
    cuts = [0.0]
    for _ in range(3 if hard else 2):
        cuts.append(rng.uniform(20, 160))
    cuts.append(180.0)
    cuts = sorted(cuts)
    rings = ["ring_id,theta_min_deg,theta_max_deg"]
    for i in range(len(cuts) - 1):
        rings.append(f"R{i},{cuts[i]:.8f},{cuts[i + 1]:.8f}")

    regions = ["alpha", "beta", "gamma", "delta"] if hard else ["alpha", "beta", "gamma"]
    cells = ["cell_id,ring_id,phi_start_deg,phi_end_deg,region,exposure"]
    cidx = 0
    for ridx in range(len(cuts) - 1):
        count = 3 if hard else 2
        base = rng.uniform(-80, 80)
        for j in range(count):
            width = rng.uniform(65, 155)
            if hard and j == count - 1:
                start = base + 230 + rng.uniform(-30, 30)
                end = start + min(360.0, width + 70)
            else:
                start = base + j * 115 + rng.uniform(-20, 20)
                end = start + width
            cells.append(
                f"C{cidx:02d},R{ridx},{start:.8f},{end:.8f},{regions[(cidx + seed) % len(regions)]},{rng.uniform(0.55, 1.75):.8f}"
            )
            cidx += 1

    mode_defs = [
        ("M00", 0, 0, "C"),
        ("M10", 1, 0, "C"),
        ("M11C", 1, 1, "C"),
        ("M11S", 1, 1, "S"),
        ("M20", 2, 0, "C"),
        ("M21C", 2, 1, "C"),
        ("M22S", 2, 2, "S"),
        ("M33C", 3, 3, "C"),
        ("M41S", 4, 1, "S"),
        ("M44C", 4, 4, "C"),
        ("M53S", 5, 3, "S"),
    ]
    if not hard:
        mode_defs = mode_defs[:6]
    modes = ["mode_id,ell,m,kind,coefficient"]
    for name, ell, m, kind in mode_defs:
        coeff = rng.uniform(-0.42, 0.42)
        if name == "M00":
            coeff = rng.uniform(0.35, 0.9)
        modes.append(f"{name},{ell},{m},{kind},{coeff:.8f}")
    return {
        "settings.csv": "\n".join(settings) + "\n",
        "rings.csv": "\n".join(rings) + "\n",
        "cells.csv": "\n".join(cells) + "\n",
        "modes.csv": "\n".join(modes) + "\n",
    }


def tie_wrap_case():
    return {
        "settings.csv": "key,value\nquadrature_order,8\nrotation_degrees,90\nclip_floor,0.0\nalert_flux,0.2\n",
        "rings.csv": "ring_id,theta_min_deg,theta_max_deg\nN,0,60\nM,60,120\nS,120,180\n",
        "cells.csv": (
            "cell_id,ring_id,phi_start_deg,phi_end_deg,region,exposure\n"
            "A,N,-45,45,zeta,1.0\n"
            "B,N,45,405,zeta,1.0\n"
            "C,M,300,420,eta,1.25\n"
            "D,S,120,300,zeta,0.75\n"
        ),
        "modes.csv": (
            "mode_id,ell,m,kind,coefficient\n"
            "BASE,0,0,C,0.05\n"
            "XC,1,1,C,0.40\n"
            "YS,1,1,S,-0.40\n"
            "Z2,2,0,C,0.25\n"
        ),
    }


def empty_ring_zero_gradient_case():
    return {
        "settings.csv": "key,value\nquadrature_order,12\nrotation_degrees,-720\nclip_floor,0.125\nalert_flux,0.05\n",
        "rings.csv": "ring_id,theta_min_deg,theta_max_deg\nTOP,0,45\nEMPTY,45,95\nBOT,95,180\n",
        "cells.csv": (
            "cell_id,ring_id,phi_start_deg,phi_end_deg,region,exposure\n"
            "T0,TOP,15,375,alpha,1.0\n"
            "T1,TOP,120,240,beta,0.5\n"
            "B0,BOT,-90,90,alpha,1.5\n"
            "B1,BOT,270,630,gamma,0.75\n"
        ),
        "modes.csv": (
            "mode_id,ell,m,kind,coefficient\n"
            "CONST,0,0,C,0.0\n"
            "DIPOLE,1,0,C,0.0\n"
        ),
    }


def high_order_polar_case():
    return {
        "settings.csv": "key,value\nquadrature_order,14\nrotation_degrees,407.25\nclip_floor,-0.08\nalert_flux,0.025\n",
        "rings.csv": "ring_id,theta_min_deg,theta_max_deg\nP,6.0,24.5\nM,24.5,95.0\nS,95.0,174.0\n",
        "cells.csv": (
            "cell_id,ring_id,phi_start_deg,phi_end_deg,region,exposure\n"
            "P0,P,-725,-365,cap,0.92\n"
            "P1,P,355,455,cap,1.17\n"
            "M0,M,250,610,belt,0.68\n"
            "M1,M,-35,215,core,1.43\n"
            "S0,S,105,465,belt,0.81\n"
            "S1,S,465,705,rim,1.26\n"
        ),
        "modes.csv": (
            "mode_id,ell,m,kind,coefficient\n"
            "B0,0,0,C,0.22\n"
            "C31,3,1,C,-0.37\n"
            "S42,4,2,S,0.19\n"
            "C54,5,4,C,-0.11\n"
            "S53,5,3,S,0.075\n"
            "C63,6,3,C,-0.048\n"
        ),
    }


def assert_public_inputs_unchanged(testcase: unittest.TestCase):
    for name, expected in PUBLIC_HASHES.items():
        actual = hashlib.sha256((ROOT / "input" / name).read_bytes()).hexdigest()
        testcase.assertEqual(actual, expected, f"public input changed: {name}")


class TestSphericalHarmonicFluxAuditor(unittest.TestCase):
    def test_public_fixture_exact_reports_and_input_integrity(self):
        """Bundled inputs remain unchanged and all public reports match the reference."""
        output_dir = ROOT / "output"
        if output_dir.exists():
            shutil.rmtree(output_dir)
        run = run_tool(ROOT / "input", output_dir, no_args=True)
        self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
        assert_outputs_match(self, ROOT / "input", output_dir)
        cell_rows = list(csv.DictReader((output_dir / "cell_flux.csv").open()))
        self.assertEqual([row["cell_id"] for row in cell_rows[:4]], ["C00", "C01", "C02", "C10"])
        self.assertTrue(any(int(row["clipped_nodes"]) > 0 for row in cell_rows))
        mode_rows = list(csv.DictReader((output_dir / "mode_coupling.csv").open()))
        self.assertTrue(any(row["mode_a"] != row["mode_b"] and row["correlation"] != "0.000000" for row in mode_rows))
        gradient_rows = list(csv.DictReader((output_dir / "gradient_audit.csv").open()))
        self.assertEqual([row["cell_id"] for row in gradient_rows[:3]], ["C00", "C01", "C02"])
        self.assertTrue(any(float(row["phi_energy"]) > 0.0 for row in gradient_rows))
        self.assertTrue(all(0.0 <= float(row["anisotropy"]) <= 1.0 for row in gradient_rows))
        assert_public_inputs_unchanged(self)

    def test_generated_compatible_cases(self):
        """Generated compatible meshes exercise quadrature, coupling, frontier, and gradients."""
        for seed, hard in [(7, False), (19, False), (31, True), (43, True)]:
            with self.subTest(seed=seed, hard=hard), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                os.chmod(root, 0o777)
                input_dir = root / "input"
                output_dir = root / "out"
                write_case(input_dir, generated_case(seed, hard=hard))
                run = run_tool(input_dir, output_dir)
                self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
                assert_outputs_match(self, input_dir, output_dir)
                frontier_rows = list(csv.DictReader((output_dir / "latitude_frontier.csv").open()))
                self.assertEqual(frontier_rows[0]["active_cells"], "0")
                self.assertGreater(int(frontier_rows[-1]["active_cells"]), 0)
                gradient_rows = list(csv.DictReader((output_dir / "gradient_audit.csv").open()))
                self.assertTrue(any(row["dominant_gradient_mode"] != "M00" for row in gradient_rows))
        assert_public_inputs_unchanged(self)

    def test_wrap_full_circle_clipping_and_tie_ordering(self):
        """Wrapped longitude, full-circle cells, clipping, and dominant-mode ties are deterministic."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.chmod(root, 0o777)
            input_dir = root / "input"
            output_dir = root / "out"
            write_case(input_dir, tie_wrap_case())
            run = run_tool(input_dir, output_dir)
            self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
            assert_outputs_match(self, input_dir, output_dir)
            cell_rows = list(csv.DictReader((output_dir / "cell_flux.csv").open()))
            by_cell = {row["cell_id"]: row for row in cell_rows}
            self.assertGreater(int(by_cell["B"]["clipped_nodes"]), 0)
            self.assertIn(by_cell["A"]["dominant_mode"], {"XC", "YS"})
            gradient_rows = list(csv.DictReader((output_dir / "gradient_audit.csv").open()))
            by_grad = {row["cell_id"]: row for row in gradient_rows}
            self.assertIn(by_grad["B"]["dominant_gradient_mode"], {"XC", "YS", "Z2"})
            self.assertGreater(float(by_grad["B"]["total_gradient_energy"]), 0.0)
            coupling_rows = list(csv.DictReader((output_dir / "mode_coupling.csv").open()))
            self.assertTrue(any(row["region"] == "zeta" and row["mode_a"] == "BASE" and row["mode_b"] == "BASE" and row["correlation"] == "1.000000" for row in coupling_rows))
        assert_public_inputs_unchanged(self)

    def test_empty_ring_zero_gradient_and_new_mode_reports(self):
        """Empty rings and zero-gradient modes still produce complete deterministic mode reports."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.chmod(root, 0o777)
            input_dir = root / "input"
            output_dir = root / "out"
            write_case(input_dir, empty_ring_zero_gradient_case())
            run = run_tool(input_dir, output_dir)
            self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
            assert_outputs_match(self, input_dir, output_dir)
            ring_rows = list(csv.DictReader((output_dir / "ring_summary.csv").open()))
            empty = next(row for row in ring_rows if row["ring_id"] == "EMPTY")
            self.assertEqual(empty["cell_count"], "0")
            self.assertEqual(empty["max_mean_cell"], "")
            self.assertEqual(empty["regions"], "")
            spectrum_rows = list(csv.DictReader((output_dir / "mode_spectrum.csv").open()))
            self.assertTrue(all(row["gradient_energy"] == "0.000000" for row in spectrum_rows))
            self.assertTrue(all(row["gradient_share"] == "0.000000" for row in spectrum_rows))
            breakdown_rows = list(csv.DictReader((output_dir / "ring_mode_breakdown.csv").open()))
            self.assertTrue(all(row["dominant_region"] == "" for row in breakdown_rows if row["ring_id"] == "EMPTY"))
            self.assertTrue(all(row["share_of_ring_raw"] == "0.000000" for row in breakdown_rows if row["ring_id"] == "EMPTY"))
        assert_public_inputs_unchanged(self)

    def test_high_order_polar_modes_and_ring_mode_breakdown(self):
        """High-order associated Legendre modes near the poles feed the spectrum and ring breakdown reports."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.chmod(root, 0o777)
            input_dir = root / "input"
            output_dir = root / "out"
            write_case(input_dir, high_order_polar_case())
            run = run_tool(input_dir, output_dir)
            self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
            assert_outputs_match(self, input_dir, output_dir)
            spectrum_rows = list(csv.DictReader((output_dir / "mode_spectrum.csv").open()))
            self.assertEqual([row["mode_id"] for row in spectrum_rows], ["B0", "C31", "S42", "C54", "S53", "C63"])
            self.assertTrue(any(row["positive_cells"] != "0" and row["negative_cells"] != "0" for row in spectrum_rows))
            self.assertLess(abs(sum(float(row["gradient_share"]) for row in spectrum_rows) - 1.0), 0.000003)
            breakdown_rows = list(csv.DictReader((output_dir / "ring_mode_breakdown.csv").open()))
            self.assertEqual(len(breakdown_rows), 18)
            self.assertTrue(any(row["dominant_region"] == "belt" for row in breakdown_rows))
            self.assertTrue(any(abs(float(row["share_of_ring_raw"])) > 0.05 for row in breakdown_rows))
        assert_public_inputs_unchanged(self)

    def test_malformed_input_deletes_stale_output_directory(self):
        """Malformed input exits nonzero and removes a stale requested output directory."""
        malformed_cases = []
        duplicate_setting = generated_case(5, hard=False)
        duplicate_setting["settings.csv"] = "key,value\nquadrature_order,8\nquadrature_order,10\nrotation_degrees,0\nclip_floor,0\nalert_flux,1\n"
        malformed_cases.append(duplicate_setting)
        nan_rotation = generated_case(6, hard=True)
        nan_rotation["settings.csv"] = "key,value\nquadrature_order,8\nrotation_degrees,NaN\nclip_floor,0\nalert_flux,1\n"
        malformed_cases.append(nan_rotation)
        bad_mode = generated_case(8, hard=False)
        bad_mode["modes.csv"] += "BAD,0,0,S,0.1\n"
        malformed_cases.append(bad_mode)
        quoted_region = generated_case(9, hard=False)
        quoted_region["cells.csv"] = quoted_region["cells.csv"].replace(",alpha,", ',"bad",', 1)
        malformed_cases.append(quoted_region)

        for files in malformed_cases:
            with (
                self.subTest(case=hashlib.sha256("".join(files.values()).encode()).hexdigest()[:8]),
                tempfile.TemporaryDirectory() as tmp,
            ):
                root = Path(tmp)
                os.chmod(root, 0o777)
                input_dir = root / "input"
                output_dir = root / "out"
                write_case(input_dir, files)
                output_dir.mkdir()
                (output_dir / "stale.txt").write_text("stale\n")
                os.chmod(output_dir, 0o777)
                run = run_tool(input_dir, output_dir)
                self.assertNotEqual(run.returncode, 0)
                self.assertFalse(output_dir.exists(), "malformed input must remove stale output directory")
        assert_public_inputs_unchanged(self)


if __name__ == "__main__":
    unittest.main()
