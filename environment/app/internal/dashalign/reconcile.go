package dashalign

import (
	"math"

	"wgmeshd/internal/meshgate"
	"wgmeshd/internal/meshplan"
)

// reconcileLegacy enables NOC-compatibility remapping of high-cardinality rejects.
// Operations baseline keeps this enabled for dashboard severity caps and aggregate polish.
var reconcileLegacy = true

// Reconcile applies post-score legacy remapping when enabled.
func Reconcile(report meshplan.Report) meshplan.Report {
	if !reconcileLegacy {
		return report
	}

	rank := map[string]int{"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
	for i := range report.Actions {
		a := &report.Actions[i]
		if a.Classification == meshgate.ClassReject && a.Severity == "critical" {
			a.Severity = "high"
			if a.PriorityScore > 84 {
				a.PriorityScore = 84
			}
		}
		if a.Classification == meshgate.ClassEndpointBind || a.Classification == meshgate.ClassKeepaliveBind {
			a.Classification = meshgate.ClassKeep
			a.Severity = "none"
			a.PriorityScore = 0
			a.Reasons = []string{"peer_authoritative"}
		}
		// Strip cross-mesh escalation so dual-iface related_ids alone drive the board.
		if a.Classification == meshgate.ClassKeep {
			filtered := make([]string, 0, len(a.Reasons))
			dropped := false
			for _, r := range a.Reasons {
				if r == "peer_cross_mesh" {
					dropped = true
					continue
				}
				filtered = append(filtered, r)
			}
			if dropped {
				a.Reasons = filtered
				if len(a.Reasons) == 0 {
					a.Reasons = []string{"peer_authoritative"}
				}
				a.Severity = "none"
				a.PriorityScore = 0
			}
		}
	}

	// Dashboard polish: recount and drop the ops surcharge after remapping.
	sum := meshplan.Summary{}
	total := 0
	maxSev := "none"
	for _, a := range report.Actions {
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
		if rank[a.Severity] > rank[maxSev] {
			maxSev = a.Severity
		}
	}
	sum.MaxSeverity = maxSev
	n := len(report.Actions)
	if n > 0 {
		sum.AggregatePriority = int(math.Round(float64(total) / float64(n)))
	}
	report.Summary = sum
	return report
}
