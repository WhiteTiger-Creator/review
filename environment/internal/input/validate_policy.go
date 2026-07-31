package input

import (
	"errors"
	"fmt"

	"racklight/drainwave/internal/model"
)

func validatePolicy(policy model.Policy, nodes map[string]model.Node) error {
	if len(policy.Targets) == 0 || len(policy.Targets) > 12 || policy.MaxWaveSize < 1 || policy.MaxWaveSize > len(policy.Targets) {
		return errors.New("invalid target count")
	}
	if !boundedNonNegativeMap(policy.MinAvailable) || !boundedNonNegativeMap(policy.ZoneParallel) || !boundedNonNegativeMap(policy.RackPowerLimit) || !boundedNonNegativeMap(policy.Cooldown) || policy.Precedence == nil || policy.Cohorts == nil || policy.Separation == nil || policy.RollingLimits == nil || policy.RiskWeights == nil {
		return errors.New("invalid policy collection")
	}
	targets := map[string]bool{}
	for _, target := range policy.Targets {
		node, exists := nodes[target]
		if !exists || !addUnique(targets, target) {
			return errors.New("invalid target")
		}
		if _, exists := policy.ZoneParallel[node.Zone]; !exists {
			return errors.New("missing zone limit")
		}
		if _, exists := policy.RackPowerLimit[node.Rack]; !exists {
			return errors.New("missing rack limit")
		}
	}
	edges := map[string]bool{}
	for _, edge := range policy.Precedence {
		if len(edge) != 2 || edge[0] == edge[1] || !targets[edge[0]] || !targets[edge[1]] {
			return errors.New("invalid precedence")
		}
		key := fmt.Sprintf("%d:%s%d:%s", len(edge[0]), edge[0], len(edge[1]), edge[1])
		if edges[key] {
			return errors.New("duplicate precedence")
		}
		edges[key] = true
	}
	return nil
}
