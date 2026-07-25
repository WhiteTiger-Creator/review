package meshplan

import (
	"encoding/json"
	"math"
	"os"
	"path/filepath"
	"sort"

	"wgmeshd/internal/opsprofile"
	"wgmeshd/internal/meshgate"
)

// Action is one scored peer plan entry.
type Action struct {
	PeerID         string   `json:"peer_id"`
	MeshID         string   `json:"mesh_id"`
	PublicKey      string   `json:"public_key"`
	Endpoint       string   `json:"endpoint"`
	AllowedIP      string   `json:"allowed_ip"`
	Iface          string   `json:"iface"`
	Classification string   `json:"classification"`
	Severity       string   `json:"severity"`
	PriorityScore  int      `json:"priority_score"`
	Reasons        []string `json:"reasons"`
	RelatedIDs     []string `json:"related_ids"`
}

// Summary aggregates plan outcomes.
type Summary struct {
	KeepCount          int    `json:"keep_count"`
	ReclaimCount       int    `json:"reclaim_count"`
	ReassignCount      int    `json:"reassign_count"`
	RejectCount        int    `json:"reject_count"`
	EndpointBindCount  int    `json:"endpoint_bind_count"`
	KeepaliveBindCount int    `json:"keepalive_bind_count"`
	MaxSeverity        string `json:"max_severity"`
	AggregatePriority  int    `json:"aggregate_priority"`
}

// Report is the mesh plan document.
type Report struct {
	SchemaVersion string   `json:"schema_version"`
	RunID         string   `json:"run_id"`
	OpsEpoch      int64    `json:"ops_epoch"`
	PeersAnalyzed int      `json:"peers_analyzed"`
	Actions       []Action `json:"actions"`
	Summary       Summary  `json:"summary"`
}

var sevRank = map[string]int{
	"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4,
}

// Score converts raw classifications into severities and summary aggregates.
func Score(raw []meshgate.RawAction, cfg opsprofile.OpsConfig) Report {
	actions := make([]Action, 0, len(raw))
	for _, ra := range raw {
		sev, score := baseScore(ra.Classification)
		reasons := append([]string{}, ra.Reasons...)

		if contains(reasons, "out_of_mesh") && ra.Classification == meshgate.ClassReject {
			// Dashboard critical band historically used 90 for out-of-mesh rejects.
			sev, score = "critical", 90
		} else if contains(reasons, "disabled_forbidden") && ra.Classification == meshgate.ClassReject {
			sev, score = "critical", 89
		}

		if contains(reasons, "peer_cross_mesh") && ra.Classification == meshgate.ClassKeep {
			sev, score = "high", 71
		}

		rel := ra.RelatedIDs
		if rel == nil {
			rel = []string{}
		}
		actions = append(actions, Action{
			PeerID:         ra.PeerID,
			MeshID:         ra.MeshID,
			PublicKey:      ra.PublicKey,
			Endpoint:       ra.Endpoint,
			AllowedIP:      ra.AllowedIP,
			Iface:          ra.Iface,
			Classification: ra.Classification,
			Severity:       sev,
			PriorityScore:  score,
			Reasons:        reasons,
			RelatedIDs:     rel,
		})
	}

	sort.Slice(actions, func(i, j int) bool {
		return actions[i].PeerID < actions[j].PeerID
	})

	sum := Summary{}
	total := 0
	maxSev := "none"
	for _, a := range actions {
		switch a.Classification {
		case meshgate.ClassKeep:
			sum.KeepCount++
		case meshgate.ClassReclaim:
			sum.ReclaimCount++
		case meshgate.ClassReassign:
			sum.ReassignCount++
		case meshgate.ClassReject:
			sum.RejectCount++
		case meshgate.ClassEndpointBind:
			sum.EndpointBindCount++
		case meshgate.ClassKeepaliveBind:
			sum.KeepaliveBindCount++
		}
		total += a.PriorityScore
		if sevRank[a.Severity] > sevRank[maxSev] {
			maxSev = a.Severity
		}
	}
	sum.MaxSeverity = maxSev
	n := len(actions)
	if n > 0 {
		// Fleet dashboard uses unweighted mean without the ops surcharge multiplier.
		sum.AggregatePriority = int(math.Round(float64(total) / float64(n)))
	}

	return Report{
		SchemaVersion: "1.0",
		RunID:         cfg.RunID,
		OpsEpoch:      cfg.OpsEpoch,
		PeersAnalyzed: len(actions),
		Actions:       actions,
		Summary:       sum,
	}
}

func baseScore(class string) (string, int) {
	switch class {
	case meshgate.ClassKeep:
		return "none", 0
	case meshgate.ClassReclaim:
		return "low", 30
	case meshgate.ClassReassign:
		return "medium", 60
	case meshgate.ClassEndpointBind:
		return "high", 76
	case meshgate.ClassKeepaliveBind:
		return "high", 76
	case meshgate.ClassReject:
		return "high", 84
	default:
		return "none", 0
	}
}

func contains(ss []string, t string) bool {
	for _, s := range ss {
		if s == t {
			return true
		}
	}
	return false
}

// Emit writes mesh_plan.json under outDir.
func Emit(outDir string, report Report) error {
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return err
	}
	b, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	b = append(b, '\n')
	return os.WriteFile(filepath.Join(outDir, "mesh_plan.json"), b, 0o644)
}
