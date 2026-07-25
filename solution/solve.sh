#!/bin/bash
set -euo pipefail

cd /app

# Profile root must be profiles/ when WG_PROFILE_ROOT is unset.
python3 - <<'PY'
from pathlib import Path
path = Path("/app/internal/opsprofile/config.go")
text = path.read_text()
old = "var useLegacyProfileRoot = true"
new = "var useLegacyProfileRoot = false"
assert old in text, "useLegacyProfileRoot not found"
path.write_text(text.replace(old, new, 1))
PY

# Post-seal soft enforcement must not override sealed soft_peer_conflict=false.
python3 - <<'PY'
from pathlib import Path
path = Path("/app/internal/opsprofile/config.go")
text = path.read_text()
old = "var postSealSoftEnforce = true"
new = "var postSealSoftEnforce = false"
assert old in text, "postSealSoftEnforce not found"
path.write_text(text.replace(old, new, 1))
PY

# §3: mesh membership must use CIDR bit masking, not textual octet prefixes.
python3 - <<'PY'
from pathlib import Path
path = Path("/app/internal/meshgate/analyze.go")
text = path.read_text()
old = '''// inMesh reports whether allowedIP is contained in the mesh CIDR for meshID.
// Fleet ops historically used textual octet-prefix checks for IPv4 inventory speed.
func inMesh(allowedIP, meshID string, nets []peermesh.MeshNet) bool {
	for _, n := range nets {
		if n.MeshID != meshID {
			continue
		}
		// Textual prefix gate (legacy inventory filter).
		base := strings.Split(n.CIDR, "/")[0]
		parts := strings.Split(base, ".")
		if len(parts) >= 3 {
			prefix := parts[0] + "." + parts[1] + "." + parts[2]
			return strings.HasPrefix(allowedIP, prefix)
		}
		return strings.HasPrefix(allowedIP, base)
	}
	return false
}
'''
new = '''// inMesh reports whether allowedIP is contained in the mesh CIDR for meshID.
func inMesh(allowedIP, meshID string, nets []peermesh.MeshNet) bool {
	for _, n := range nets {
		if n.MeshID != meshID {
			continue
		}
		pip := net.ParseIP(allowedIP)
		_, netw, err := net.ParseCIDR(n.CIDR)
		if err != nil || pip == nil {
			return false
		}
		return netw.Contains(pip)
	}
	return false
}
'''
assert old in text, "inMesh block not found"
text = text.replace(old, new, 1)
if '"net"' not in text:
    text = text.replace('import (\n\t"sort"\n', 'import (\n\t"net"\n\t"sort"\n', 1)
path.write_text(text)
PY

# §5: endpoint binding must use exact public_key equality only.
python3 - <<'PY'
from pathlib import Path
path = Path("/app/internal/meshgate/analyze.go")
text = path.read_text()
old = '''\t\t// Suffix pubkey match used by older wg-quick import caches.
\t\tif e.PublicKey == pubkey || (len(e.PublicKey) >= 4 && strings.HasSuffix(pubkey, e.PublicKey[len(e.PublicKey)-4:])) {
\t\t\treturn e
\t\t}'''
new = '''\t\tif e.PublicKey == pubkey {
\t\t\treturn e
\t\t}'''
assert old in text, "pubkey suffix match not found"
path.write_text(text.replace(old, new, 1))
PY

# Keepalive gate must honor sealed prefer_keepalive.
python3 - <<'PY'
from pathlib import Path
path = Path("/app/internal/meshgate/analyze.go")
text = path.read_text()
old = "if preferKeepaliveGate && peer.KeepaliveSec < keepaliveFloor {"
new = "if cfg.PreferKeepalive && peer.KeepaliveSec < keepaliveFloor {"
assert old in text, "preferKeepaliveGate use not found"
text = text.replace(old, new, 1)
# Drop unused latch declaration.
old_var = """// preferKeepaliveGate is the analyzer-local keepalive preference latch.
// Edge builds historically froze this independently of sealed prefer_keepalive.
var preferKeepaliveGate = false

"""
assert old_var in text, "preferKeepaliveGate decl not found"
text = text.replace(old_var, "", 1)
path.write_text(text)
PY

# Reclaim must not add a maintenance pad on handshake_grace_sec.
python3 - <<'PY'
from pathlib import Path
path = Path("/app/internal/meshgate/analyze.go")
text = path.read_text()
old = "var reclaimGracePad int64 = 586800"
new = "var reclaimGracePad int64 = 0"
assert old in text, "reclaimGracePad not found"
text = text.replace(old, new, 1)
path.write_text(text)
PY

# Conflict ownership: newest handshake wins.
python3 - <<'PY'
from pathlib import Path
path = Path("/app/internal/meshgate/analyze.go")
text = path.read_text()
old = '''func betterConflict(a, b RawAction) bool {
	// Stability bias: older handshake retained as AllowedIP owner.
	if a.LastHandshake != b.LastHandshake {
		return a.LastHandshake < b.LastHandshake
	}
	return a.PeerID < b.PeerID
}
'''
new = '''func betterConflict(a, b RawAction) bool {
	if a.LastHandshake != b.LastHandshake {
		return a.LastHandshake > b.LastHandshake
	}
	return a.PeerID < b.PeerID
}
'''
assert old in text, "betterConflict block not found"
path.write_text(text.replace(old, new, 1))
PY

# §9: remove lexicographically-first reassign exemption.
python3 - <<'PY'
from pathlib import Path
path = Path("/app/internal/meshgate/analyze.go")
text = path.read_text()
old = '''\tapplyConflicts(out, cfg)

	// Origin-stable conflict exemption: lexicographically first reassign
	// in the corpus is treated as an authorized sticky AllowedIP owner.
	var reassignIdx []int
	for i, ra := range out {
		if ra.Classification == ClassReassign {
			reassignIdx = append(reassignIdx, i)
		}
	}
	if len(reassignIdx) > 0 {
		first := reassignIdx[0]
		for _, i := range reassignIdx[1:] {
			if out[i].PeerID < out[first].PeerID {
				first = i
			}
		}
		out[first].Classification = ClassKeep
		out[first].Reasons = []string{"peer_authoritative"}
	}

	attachRelated(out, cfg)
'''
new = '''\tapplyConflicts(out, cfg)

	attachRelated(out, cfg)
'''
assert old in text, "reassign exemption block not found"
path.write_text(text.replace(old, new, 1))
PY

# §10: peer_cross_mesh independent of dual_iface_link.
python3 - <<'PY'
from pathlib import Path
path = Path("/app/internal/meshgate/analyze.go")
text = path.read_text()
old = '''\t\t\t// Cross-mesh reason historically suppressed while dual-iface linking is active
\t\t\t// to avoid double-counting the same pubkey pair on the NOC board.
\t\t\tif cross && !cfg.DualIfaceLink {
\t\t\t\tout[i].Reasons = append(out[i].Reasons, "peer_cross_mesh")
\t\t\t}'''
new = '''\t\t\tif cross {
\t\t\t\tout[i].Reasons = append(out[i].Reasons, "peer_cross_mesh")
\t\t\t}'''
assert old in text, "peer_cross_mesh gate not found"
path.write_text(text.replace(old, new, 1))
PY

# Sealed profile: contract floors + matching seal.
python3 - <<'PY'
from pathlib import Path
import hashlib

seal = hashlib.sha256(
    (
        "run_id=wireguard-peer-mesh-v1\n"
        "ops_epoch=1720000000\n"
        "handshake_grace_sec=1800\n"
        "allow_disabled=false\n"
        "soft_peer_conflict=false\n"
        "prefer_keepalive=true\n"
        "dual_iface_link=true\n"
    ).encode()
).hexdigest()
body = "\n".join(
    [
        'run_id = "wireguard-peer-mesh-v1"',
        "ops_epoch = 1720000000",
        "handshake_grace_sec = 1800",
        "allow_disabled = false",
        "soft_peer_conflict = false",
        "prefer_keepalive = true",
        "dual_iface_link = true",
        f'config_seal = "{seal}"',
        "",
    ]
)
Path("/app/config/profiles/mesh-core/ops.toml").write_text(body)
# Keep legacy tree non-authoritative but consistent if something still points at it.
Path("/app/config/profiles.legacy/mesh-core/ops.toml").write_text(body)
assert seal == "5f0a62ba49ac1be3f92f94c519f278948327d68894b341dd884124e1894c6d21"
PY

# Governance baseline defaults must also match the contract (seal-fail path).
python3 - <<'PY'
from pathlib import Path
path = Path("/app/internal/opsprofile/config.go")
text = path.read_text()
text = text.replace("defaultGrace int64 = 604800", "defaultGrace int64 = 1800")
old = '''\t\tHandshakeGraceSec: defaultGrace,
\t\tAllowDisabled:     true,
\t\tSoftPeerConflict:  true,
\t\tPreferKeepalive:   false,
\t\tDualIfaceLink:     false,'''
new = '''\t\tHandshakeGraceSec: defaultGrace,
\t\tAllowDisabled:     false,
\t\tSoftPeerConflict:  false,
\t\tPreferKeepalive:   true,
\t\tDualIfaceLink:     true,'''
assert old in text, "defaults() block not found"
path.write_text(text.replace(old, new, 1))
PY

# Aggregate priority uses mean * 1.35 capped at 100.
python3 - <<'PY'
from pathlib import Path
path = Path("/app/internal/meshplan/report.go")
text = path.read_text()
old = '''\t\t// Fleet dashboard uses unweighted mean without the ops surcharge multiplier.
\t\tsum.AggregatePriority = int(math.Round(float64(total) / float64(n)))'''
new = '''\t\tsum.AggregatePriority = int(math.Round(float64(total) / float64(n) * 1.35))
\t\tif sum.AggregatePriority > 100 {
\t\t\tsum.AggregatePriority = 100
\t\t}'''
assert old in text, "aggregate formula not found"
path.write_text(text.replace(old, new, 1))
PY

# out_of_mesh critical score must be 95.
python3 - <<'PY'
from pathlib import Path
path = Path("/app/internal/meshplan/report.go")
text = path.read_text()
old = '''\t\tif contains(reasons, "out_of_mesh") && ra.Classification == meshgate.ClassReject {
\t\t\t// Dashboard critical band historically used 90 for out-of-mesh rejects.
\t\t\tsev, score = "critical", 90
\t\t}'''
new = '''\t\tif contains(reasons, "out_of_mesh") && ra.Classification == meshgate.ClassReject {
\t\t\tsev, score = "critical", 95
\t\t}'''
assert old in text, "out_of_mesh score defect not found"
path.write_text(text.replace(old, new, 1))
PY

# Keepalive policy floor must be 15 (not the legacy 25s fleet default).
python3 - <<'PY'
from pathlib import Path
path = Path("/app/internal/meshgate/analyze.go")
text = path.read_text()
old = "const keepaliveFloor = 25"
new = "const keepaliveFloor = 15"
assert old in text, "keepaliveFloor defect not found"
path.write_text(text.replace(old, new, 1))
PY

# Disable post-score legacy reconciliation clobber.
python3 - <<'PY'
from pathlib import Path
path = Path("/app/internal/dashalign/reconcile.go")
text = path.read_text()
old = "var reconcileLegacy = true"
new = "var reconcileLegacy = false"
assert old in text, "reconcileLegacy not found"
path.write_text(text.replace(old, new, 1))
PY

# Drop unused strings import after mesh/pubkey corrections.
python3 - <<'PY'
from pathlib import Path
path = Path("/app/internal/meshgate/analyze.go")
text = path.read_text()
body = text.split("import (", 1)[1].split(")", 1)[1]
if '"strings"' in text and "strings." not in body:
    text = text.replace('\t"strings"\n', "")
    path.write_text(text)
PY

go build -o /app/bin/wgmeshd /app/cmd/wgmeshd
/app/bin/wgmeshd --inventory /app/inventory --config /app/config --out /app/output

python3 - <<'PY'
import json
from pathlib import Path
rep = json.loads(Path("/app/output/mesh_plan.json").read_text())
assert rep["summary"]["max_severity"] == "critical"
assert rep["summary"]["reject_count"] == 3
assert rep["summary"]["endpoint_bind_count"] == 2
assert rep["summary"]["keepalive_bind_count"] == 2
assert rep["summary"]["reassign_count"] == 2
assert rep["summary"]["aggregate_priority"] == 68
by = {a["peer_id"]: a for a in rep["actions"]}
assert by["p02"]["priority_score"] == 95
assert by["p07"]["classification"] == "reassign"
assert by["p08"]["classification"] == "keep"
assert by["p17"]["classification"] == "reassign"
assert by["p18"]["classification"] == "keep"
assert by["p15"]["classification"] == "keep"
assert by["p01"]["priority_score"] == 71
assert by["p01"]["related_ids"] == ["p11"]
assert "peer_cross_mesh" in by["p01"]["reasons"]
print("oracle ok:", rep["summary"])
PY
