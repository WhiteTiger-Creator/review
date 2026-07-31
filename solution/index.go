package planner

import (
	"sort"

	"racklight/drainwave/internal/model"
)

type separationRule struct {
	left  uint16
	right uint16
	gap   int
}

type maskFacts struct {
	valid            bool
	required         uint16
	cooldownServices uint16
	rollingCounts    [16]uint8
	risk             int
	names            []string
}

type context struct {
	targets      []string
	nodes        map[string]model.Node
	predecessors []uint16
	cohortMasks  []uint16
	separation   []separationRule
	serviceTotal map[string]int
	cooldownKeys []string
	cooldownPos  map[string]int
	rollingKeys  []string
	historyDepth int
	policy       model.Policy
	facts        []maskFacts
	candidates   []uint16
}

func newContext(inventory model.Inventory, policy model.Policy) context {
	nodes := make(map[string]model.Node, len(inventory.Nodes))
	serviceTotal := map[string]int{}
	for _, node := range inventory.Nodes {
		nodes[node.ID] = node
		for _, service := range node.Services {
			serviceTotal[service]++
		}
	}
	targets := append([]string(nil), policy.Targets...)
	sort.Strings(targets)
	positions := map[string]int{}
	for index, id := range targets {
		positions[id] = index
	}
	predecessors := make([]uint16, len(targets))
	for _, edge := range policy.Precedence {
		predecessors[positions[edge[1]]] |= uint16(1) << positions[edge[0]]
	}
	cohortMasks := make([]uint16, 0, len(policy.Cohorts))
	for _, cohort := range policy.Cohorts {
		var mask uint16
		for _, id := range cohort {
			mask |= uint16(1) << positions[id]
		}
		cohortMasks = append(cohortMasks, mask)
	}
	separation := make([]separationRule, 0, len(policy.Separation))
	historyDepth := 0
	for _, rule := range policy.Separation {
		separation = append(separation, separationRule{
			left: uint16(1) << positions[rule.Left], right: uint16(1) << positions[rule.Right], gap: rule.Gap,
		})
		if rule.Gap > historyDepth {
			historyDepth = rule.Gap
		}
	}
	for _, limit := range policy.RollingLimits {
		if limit.Window-1 > historyDepth {
			historyDepth = limit.Window - 1
		}
	}
	cooldownKeys := make([]string, 0, len(policy.Cooldown))
	for service := range policy.Cooldown {
		cooldownKeys = append(cooldownKeys, service)
	}
	sort.Strings(cooldownKeys)
	cooldownPos := make(map[string]int, len(cooldownKeys))
	for index, service := range cooldownKeys {
		cooldownPos[service] = index
	}
	rollingKeys := make([]string, 0, len(policy.RollingLimits))
	for service := range policy.RollingLimits {
		rollingKeys = append(rollingKeys, service)
	}
	sort.Strings(rollingKeys)

	ctx := context{
		targets: targets, nodes: nodes, predecessors: predecessors, cohortMasks: cohortMasks,
		separation: separation, serviceTotal: serviceTotal, cooldownKeys: cooldownKeys,
		cooldownPos: cooldownPos, rollingKeys: rollingKeys, historyDepth: historyDepth,
		policy: policy,
	}
	ctx.precomputeMasks()
	return ctx
}

func (ctx *context) precomputeMasks() {
	all := uint16(1)<<len(ctx.targets) - 1
	ctx.facts = make([]maskFacts, int(all)+1)
	for mask := uint16(1); mask <= all; mask++ {
		facts := maskFacts{names: ctx.names(mask)}
		for index := range ctx.targets {
			bit := uint16(1) << index
			if mask&bit != 0 {
				facts.required |= ctx.predecessors[index]
			}
		}
		facts.valid = ctx.validWave(mask)
		if facts.valid {
			services := ctx.services(mask)
			for service := range services {
				if index, tracked := ctx.cooldownPos[service]; tracked {
					facts.cooldownServices |= uint16(1) << index
				}
			}
			for index, service := range ctx.rollingKeys {
				facts.rollingCounts[index] = uint8(ctx.serviceCount(mask, service))
			}
			for service, weight := range ctx.policy.RiskWeights {
				count := ctx.serviceCount(mask, service)
				facts.risk += weight * count * count
			}
			ctx.candidates = append(ctx.candidates, mask)
		}
		ctx.facts[mask] = facts
	}
	sort.Slice(ctx.candidates, func(i, j int) bool {
		return ctx.lessMask(ctx.candidates[i], ctx.candidates[j])
	})
}

func (ctx context) serviceCount(mask uint16, service string) int {
	count := 0
	for index, id := range ctx.targets {
		if mask&(uint16(1)<<index) == 0 {
			continue
		}
		for _, candidate := range ctx.nodes[id].Services {
			if candidate == service {
				count++
				break
			}
		}
	}
	return count
}

func (ctx context) services(mask uint16) map[string]bool {
	values := map[string]bool{}
	for index, id := range ctx.targets {
		if mask&(uint16(1)<<index) == 0 {
			continue
		}
		for _, service := range ctx.nodes[id].Services {
			values[service] = true
		}
	}
	return values
}

func (ctx context) lessMask(left, right uint16) bool {
	leftNames := ctx.facts[left].names
	rightNames := ctx.facts[right].names
	for index := 0; index < len(leftNames) && index < len(rightNames); index++ {
		if leftNames[index] != rightNames[index] {
			return leftNames[index] < rightNames[index]
		}
	}
	return len(leftNames) < len(rightNames)
}
