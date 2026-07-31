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
	if !boundedNonNegativeMap(policy.MinAvailable) || !boundedNonNegativeMap(policy.ZoneParallel) || !boundedNonNegativeMap(policy.RackPowerLimit) {
		return errors.New("invalid limit map")
	}
	if policy.Precedence == nil || policy.Cohorts == nil || policy.Separation == nil || policy.Cooldown == nil || policy.RollingLimits == nil || policy.RiskWeights == nil {
		return errors.New("missing collection")
	}
	if len(policy.Cooldown) > 16 || len(policy.RollingLimits) > 16 || len(policy.RiskWeights) > 16 {
		return errors.New("too many tracked services")
	}
	for service, value := range policy.Cooldown {
		if service == "" || value < 0 || value > 3 {
			return errors.New("invalid cooldown")
		}
	}
	for service, limit := range policy.RollingLimits {
		if service == "" || limit.Window < 1 || limit.Window > 4 || limit.MaxUnavailable < 0 || limit.MaxUnavailable > maxContractInteger {
			return errors.New("invalid rolling limit")
		}
	}
	for service, weight := range policy.RiskWeights {
		if service == "" || weight < 1 || weight > 1000 {
			return errors.New("invalid risk weight")
		}
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
		key := directedKey(edge[0], edge[1])
		if edges[key] {
			return errors.New("duplicate precedence")
		}
		edges[key] = true
	}

	cohortMembers := map[string]bool{}
	for _, cohort := range policy.Cohorts {
		if len(cohort) < 2 || len(cohort) > 4 {
			return errors.New("invalid cohort size")
		}
		within := map[string]bool{}
		for _, target := range cohort {
			if !targets[target] || !addUnique(within, target) || cohortMembers[target] {
				return errors.New("invalid cohort member")
			}
			cohortMembers[target] = true
		}
	}

	pairs := map[string]bool{}
	for _, rule := range policy.Separation {
		if rule.Left == rule.Right || !targets[rule.Left] || !targets[rule.Right] || rule.Gap < 0 || rule.Gap > 3 {
			return errors.New("invalid separation")
		}
		left, right := rule.Left, rule.Right
		if right < left {
			left, right = right, left
		}
		key := directedKey(left, right)
		if pairs[key] {
			return errors.New("duplicate separation")
		}
		pairs[key] = true
	}
	return nil
}

func directedKey(left, right string) string {
	return fmt.Sprintf("%d:%s%d:%s", len(left), left, len(right), right)
}
