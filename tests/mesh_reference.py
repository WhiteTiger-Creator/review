import hashlib
import json
from datetime import datetime
from pathlib import Path


def get_sig(
    gw: str,
    seq: int,
    ts: str,
    unit: str,
    op: str,
    metric: str = "",
    val: float | None = None,
    offset: float | None = None,
) -> str:
    val_str = f"{val:.4f}" if val is not None else ""
    off_str = f"{offset:.4f}" if offset is not None else ""
    payload = f"{gw}|{seq}|{ts}|{unit}|{op}|{metric}|{val_str}|{off_str}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def reconcile_mesh(data_root: Path, topology: dict) -> dict:
    data_root = Path(data_root)
    gatewaysList = []
    driftList = []
    globalRecoverable = True

    if not data_root.is_dir():
        return {
            "recoverable": False,
            "gateways": [],
            "drift_events": []
        }

    gatewayDirs = sorted([d.name for d in data_root.iterdir() if d.is_dir()])

    sync_metrics = topology.get("sync_metrics", [])
    syncStats = {m: {} for m in sync_metrics}

    for gwID in gatewayDirs:
        gwDir = data_root / gwID
        segmentFiles = sorted(
            f.name
            for f in gwDir.iterdir()
            if f.is_file() and f.name.startswith("seg_") and f.name.endswith(".jsonl")
        )

        recoverable = True
        processedCount = 0
        expectedSeq = 1
        last_time = None
        unitsMap = {}

        batchOpen = False
        stagedOps = []

        def recordGwDriftEvent(seq, unit, reason, detail, _gw_id=gwID):
            driftList.append({
                "gateway_id": _gw_id,
                "seq": seq,
                "unit_id": unit,
                "reason": reason,
                "detail": detail
            })

        def commit_batch(_units_map=unitsMap):
            nonlocal stagedOps, batchOpen
            for op in stagedOps:
                uState = _units_map.get(op["unit_id"])
                if not uState or uState.get("retired", False):
                    continue
                if op["op"] == "TELEMETRY":
                    calibVal = op["val"] + uState.get("calibOffset", 0.0)
                    stats = uState["metricStats"].get(op["metric"])
                    if not stats:
                        stats = {
                            "metric": op["metric"],
                            "min": calibVal,
                            "max": calibVal,
                            "average": calibVal,
                            "count": 1,
                            "sum": calibVal
                        }
                        uState["metricStats"][op["metric"]] = stats
                    else:
                        stats["count"] += 1
                        stats["sum"] += calibVal
                        stats["min"] = min(stats["min"], calibVal)
                        stats["max"] = max(stats["max"], calibVal)
                        stats["average"] = stats["sum"] / stats["count"]
                elif op["op"] == "TUNE":
                    uState["calibOffset"] = op["offset"]
            stagedOps = []
            batchOpen = False

        for segName in segmentFiles:
            segPath = gwDir / segName
            try:
                content = segPath.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                recoverable = False
                break

            for raw_line in content.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                processedCount += 1

                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    recoverable = False
                    recordGwDriftEvent(expectedSeq, "", "bad_signature", "signature hash mismatch")
                    continue

                vfound = False
                violationReason, violationDetail = "", ""

                seq = rec.get("seq")
                ts = rec.get("ts", "")
                unit = rec.get("unit_id", "")
                op = rec.get("op", "")
                metric = rec.get("metric", "")
                val = rec.get("val")
                offset = rec.get("offset")
                sig = rec.get("sig", "")

                # 1. duplicate_seq
                if seq is not None and seq > 0 and seq < expectedSeq:
                    violationReason = "duplicate_seq"
                    violationDetail = f"duplicate sequence number: {seq}"
                    vfound = True

                # 2. invalid_seq
                if not vfound and seq != expectedSeq:
                    violationReason = "invalid_seq"
                    violationDetail = f"invalid sequence: expected {expectedSeq}, got {seq}"
                    vfound = True

                # 3. invalid_timestamp
                timestamp = None
                if not vfound:
                    try:
                        timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        if last_time is not None and timestamp < last_time:
                            violationReason = "invalid_timestamp"
                            violationDetail = f"retrogressive or invalid timestamp: {ts}"
                            vfound = True
                    except ValueError:
                        violationReason = "invalid_timestamp"
                        violationDetail = f"retrogressive or invalid timestamp: {ts}"
                        vfound = True

                # 4. unknown_op_or_metric
                if not vfound:
                    valid_ops = {"BOOT", "PING", "TELEMETRY", "TUNE", "SHUTDOWN", "BATCH_BEGIN", "BATCH_COMMIT", "BATCH_ABORT"}
                    if op not in valid_ops or (op == "TELEMETRY" and not metric):
                        violationReason = "unknown_op_or_metric"
                        violationDetail = f"unknown op '{op}' or missing metric"
                        vfound = True

                # 5. missing unit_id
                if not vfound and not unit:
                    violationReason = "unknown_op_or_metric"
                    violationDetail = f"unknown op '{op}' or missing metric"
                    vfound = True

                # 6. bad_signature
                if not vfound:
                    computed = get_sig(gwID, seq, ts, unit, op, metric, val, offset)
                    if computed != sig:
                        violationReason = "bad_signature"
                        violationDetail = "signature hash mismatch"
                        vfound = True

                # 7. transaction boundary ops
                if not vfound:
                    if op in ("BATCH_COMMIT", "BATCH_ABORT") and not batchOpen:
                        violationReason = "orphan_batch"
                        violationDetail = "batch boundary op without open transaction"
                        vfound = True
                    elif op == "BATCH_BEGIN" and batchOpen:
                        violationReason = "nested_batch"
                        violationDetail = "nested transaction begin not allowed"
                        vfound = True

                # 8. tune_missing_unit
                if not vfound and op == "TUNE":
                    uState = unitsMap.get(unit)
                    if not uState or not uState.get("discovered", False):
                        violationReason = "tune_missing_unit"
                        violationDetail = f"cannot tune undiscovered unit: {unit}"
                        vfound = True

                if vfound:
                    recordGwDriftEvent(seq, unit, violationReason, violationDetail)
                    if violationReason in ("invalid_seq", "duplicate_seq", "bad_signature"):
                        recoverable = False

                    if batchOpen:
                        stagedOps = []
                        batchOpen = False

                    if violationReason not in ("invalid_seq", "duplicate_seq"):
                        expectedSeq += 1
                    continue

                # Valid record
                expectedSeq += 1
                last_time = timestamp

                if op == "BATCH_BEGIN":
                    batchOpen = True
                    continue
                elif op == "BATCH_COMMIT":
                    commit_batch()
                    continue
                elif op == "BATCH_ABORT":
                    stagedOps = []
                    batchOpen = False
                    continue

                uState = unitsMap.get(unit)
                if not uState:
                    uState = {
                        "unitID": unit,
                        "discovered": False,
                        "retired": False,
                        "calibOffset": 0.0,
                        "metricStats": {}
                    }
                    unitsMap[unit] = uState

                if op == "BOOT":
                    uState["discovered"] = True
                    uState["retired"] = False
                else:
                    if not uState["discovered"]:
                        recordGwDriftEvent(seq, unit, "orphan_unit", f"orphan unit event: {unit}")
                        continue
                    if uState["retired"]:
                        recordGwDriftEvent(seq, unit, "stale_unit_op", f"event on retired unit: {unit}")
                        continue

                    if op == "SHUTDOWN":
                        uState["retired"] = True
                    elif op == "PING":
                        pass
                    elif op == "TUNE":
                        if batchOpen:
                            stagedOps.append({"op": "TUNE", "unit_id": unit, "offset": offset})
                        else:
                            uState["calibOffset"] = offset
                    elif op == "TELEMETRY":
                        if batchOpen:
                            stagedOps.append({"op": "TELEMETRY", "unit_id": unit, "metric": metric, "val": val})
                        else:
                            calibVal = val + uState["calibOffset"]
                            stats = uState["metricStats"].get(metric)
                            if not stats:
                                stats = {
                                    "metric": metric,
                                    "min": calibVal,
                                    "max": calibVal,
                                    "average": calibVal,
                                    "count": 1,
                                    "sum": calibVal
                                }
                                uState["metricStats"][metric] = stats
                            else:
                                stats["count"] += 1
                                stats["sum"] += calibVal
                                stats["min"] = min(stats["min"], calibVal)
                                stats["max"] = max(stats["max"], calibVal)
                                stats["average"] = stats["sum"] / stats["count"]

        if batchOpen:
            stagedOps = []
            batchOpen = False

        unitsOut = []
        if recoverable:
            for unitName in sorted(unitsMap.keys()):
                us = unitsMap[unitName]
                if not us["discovered"]:
                    continue

                mList = []
                for mName in sorted(us["metricStats"].keys()):
                    stats = us["metricStats"][mName]
                    mList.append({
                        "metric": stats["metric"],
                        "min": stats["min"],
                        "max": stats["max"],
                        "average": stats["average"],
                        "count": stats["count"]
                    })

                unitsOut.append({
                    "unit_id": us["unitID"],
                    "active": not us["retired"],
                    "metrics": mList
                })

                for mStats in mList:
                    if mStats["metric"] in syncStats:
                        syncStats[mStats["metric"]][gwID] = mStats["average"]
        else:
            globalRecoverable = False

        gatewaysList.append({
            "gateway_id": gwID,
            "recoverable": recoverable,
            "processed_records": processedCount,
            "units": unitsOut if recoverable else []
        })

    if globalRecoverable:
        # Colocation check: active units only
        paired = topology.get("bound_nodes", [])
        for pair in paired:
            left = pair["left"]
            right = pair["right"]
            for gw in gatewaysList:
                leftActive = any(u["unit_id"] == left and u["active"] for u in gw["units"])
                rightActive = any(u["unit_id"] == right and u["active"] for u in gw["units"])
                if leftActive != rightActive:
                    driftList.append({
                        "gateway_id": "",
                        "seq": 0,
                        "unit_id": "",
                        "reason": "binding_breach",
                        "detail": f"binding broken: {left} and {right} not co-present"
                    })

        # Authorized gateway check: active units only (unit_id ascending)
        authorized = topology.get("home_sites", {})
        for unit in sorted(authorized.keys()):
            allowed = authorized[unit]
            for gw in gatewaysList:
                unitActive = any(u["unit_id"] == unit and u["active"] for u in gw["units"])
                if unitActive and gw["gateway_id"] not in allowed:
                    driftList.append({
                        "gateway_id": "",
                        "seq": 0,
                        "unit_id": unit,
                        "reason": "site_forbidden",
                        "detail": f"unit {unit} seen on foreign site {gw['gateway_id']}"
                    })

        # Mirrored metrics check
        for mName in sorted(syncStats.keys()):
            gwsMap = syncStats[mName]
            if len(gwsMap) < 2:
                continue

            values = list(gwsMap.values())
            minVal = min(values)
            maxVal = max(values)
            if (maxVal - minVal) > 0.05:
                driftList.append({
                    "gateway_id": "",
                    "seq": 0,
                    "unit_id": "",
                    "reason": "sync_skew",
                    "detail": f"sync metric skew: {mName} exceeds tolerance"
                })

    # Sort violations
    driftList.sort(key=lambda x: (x["gateway_id"], x["seq"]))

    return {
        "recoverable": globalRecoverable,
        "gateways": gatewaysList,
        "drift_events": driftList
    }
