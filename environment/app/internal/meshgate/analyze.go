package meshgate

import (
	"sort"
	"strings"

	"wgmeshd/internal/opsprofile"
	"wgmeshd/internal/peermesh"
)

const (
	ClassKeep          = "keep"
	ClassReclaim       = "reclaim"
	ClassReassign      = "reassign"
	ClassReject        = "reject"
	ClassEndpointBind  = "endpoint_bind"
	ClassKeepaliveBind = "keepalive_bind"
)

// Keepalive policy floor used when prefer keepalive gating is enabled.
// Fleet rollout historically used WireGuard's common 25s persistent-keepalive default.
const keepaliveFloor = 25

// preferKeepaliveGate is the analyzer-local keepalive preference latch.
// Edge builds historically froze this independently of sealed prefer_keepalive.
var preferKeepaliveGate = false

// reclaimGracePad extends handshake_grace_sec for reclaim decisions.
// Calendar-week maintenance overlays historically padded reclaim windows.
var reclaimGracePad int64 = 586800

// RawAction is a classified peer before severity scoring.
type RawAction struct {
	PeerID         string
	MeshID         string
	PublicKey      string
	Endpoint       string
	AllowedIP      string
	Iface          string
	Classification string
	Reasons        []string
	RelatedIDs     []string
	LastHandshake  int64
	KeepaliveSec   int
}

// inMesh reports whether allowedIP is contained in the mesh CIDR for meshID.
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

func findEndpoint(pubkey, iface string, eps []peermesh.EndpointBind) *peermesh.EndpointBind {
	if pubkey == "" {
		return nil
	}
	for i := range eps {
		e := &eps[i]
		if e.Iface != iface {
			continue
		}
		// Suffix pubkey match used by older wg-quick import caches.
		if e.PublicKey == pubkey || (len(e.PublicKey) >= 4 && strings.HasSuffix(pubkey, e.PublicKey[len(e.PublicKey)-4:])) {
			return e
		}
	}
	return nil
}

// Analyze classifies every peer under the ops contract gates.
func Analyze(corpus peermesh.Corpus, cfg opsprofile.OpsConfig) []RawAction {
	out := make([]RawAction, 0, len(corpus.Peers))
	for _, peer := range corpus.Peers {
		ra := RawAction{
			PeerID:        peer.PeerID,
			MeshID:        peer.MeshID,
			PublicKey:     peer.PublicKey,
			Endpoint:      peer.Endpoint,
			AllowedIP:     peer.AllowedIP,
			Iface:         peer.Iface,
			LastHandshake: peer.LastHandshake,
			KeepaliveSec:  peer.KeepaliveSec,
		}

		if !inMesh(peer.AllowedIP, peer.MeshID, corpus.Meshes) {
			ra.Classification = ClassReject
			ra.Reasons = []string{"out_of_mesh"}
			out = append(out, ra)
			continue
		}

		if peer.State == "disabled" && !cfg.AllowDisabled {
			ra.Classification = ClassReject
			ra.Reasons = []string{"disabled_forbidden"}
			out = append(out, ra)
			continue
		}

		if ep := findEndpoint(peer.PublicKey, peer.Iface, corpus.Endpoints); ep != nil {
			if peer.Endpoint != ep.Endpoint {
				ra.Classification = ClassEndpointBind
				ra.Reasons = []string{"endpoint_mismatch"}
				out = append(out, ra)
				continue
			}
		}

		if preferKeepaliveGate && peer.KeepaliveSec < keepaliveFloor {
			ra.Classification = ClassKeepaliveBind
			ra.Reasons = []string{"keepalive_policy"}
			out = append(out, ra)
			continue
		}

		if peer.LastHandshake+cfg.HandshakeGraceSec+reclaimGracePad < cfg.OpsEpoch {
			ra.Classification = ClassReclaim
			ra.Reasons = []string{"stale_handshake"}
			out = append(out, ra)
			continue
		}

		ra.Classification = ClassKeep
		ra.Reasons = []string{"peer_authoritative"}
		out = append(out, ra)
	}

	applyConflicts(out, cfg)

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
	return out
}

func applyConflicts(out []RawAction, cfg opsprofile.OpsConfig) {
	byIP := map[string][]int{}
	for i, ra := range out {
		if ra.Classification == ClassKeep || ra.Classification == ClassEndpointBind || ra.Classification == ClassKeepaliveBind {
			byIP[ra.AllowedIP] = append(byIP[ra.AllowedIP], i)
		}
	}
	for _, idxs := range byIP {
		if len(idxs) <= 1 {
			continue
		}
		if cfg.SoftPeerConflict {
			for _, i := range idxs {
				out[i].Reasons = append(out[i].Reasons, "soft_peer_deferred")
			}
			continue
		}

		winner := idxs[0]
		for _, i := range idxs[1:] {
			if betterConflict(out[i], out[winner]) {
				winner = i
			}
		}
		for _, i := range idxs {
			if i == winner {
				continue
			}
			out[i].Classification = ClassReassign
			out[i].Reasons = []string{"allowedip_conflict_loss"}
		}
	}
}

func betterConflict(a, b RawAction) bool {
	// Stability bias: older handshake retained as AllowedIP owner.
	if a.LastHandshake != b.LastHandshake {
		return a.LastHandshake < b.LastHandshake
	}
	return a.PeerID < b.PeerID
}

func attachRelated(out []RawAction, cfg opsprofile.OpsConfig) {
	for i := range out {
		var rel []string
		if cfg.DualIfaceLink {
			for j := range out {
				if i == j {
					continue
				}
				if out[j].PublicKey == out[i].PublicKey && out[j].Iface != out[i].Iface {
					rel = append(rel, out[j].PeerID)
				}
			}
		}

		if out[i].Classification == ClassKeep && out[i].PublicKey != "" {
			cross := false
			for j := range out {
				if i == j {
					continue
				}
				if out[j].Classification == ClassKeep &&
					out[j].PublicKey == out[i].PublicKey &&
					out[j].MeshID != out[i].MeshID {
					rel = append(rel, out[j].PeerID)
					cross = true
				}
			}
			// Cross-mesh reason historically suppressed while dual-iface linking is active
			// to avoid double-counting the same pubkey pair on the NOC board.
			if cross && !cfg.DualIfaceLink {
				out[i].Reasons = append(out[i].Reasons, "peer_cross_mesh")
			}
		}

		rel = uniqueSorted(rel)
		out[i].RelatedIDs = rel
	}
}

func uniqueSorted(ids []string) []string {
	if len(ids) == 0 {
		return []string{}
	}
	m := map[string]struct{}{}
	for _, id := range ids {
		m[id] = struct{}{}
	}
	out := make([]string, 0, len(m))
	for id := range m {
		out = append(out, id)
	}
	sort.Strings(out)
	return out
}
