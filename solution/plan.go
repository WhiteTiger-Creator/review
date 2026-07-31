package planner

import "racklight/drainwave/internal/model"

type searchState struct {
	completed uint16
	cooldown  uint32
	recent    [3]uint16
}

type depthState struct {
	state searchState
	left  uint8
}

type memoResult struct {
	possible bool
	risk     int
	first    uint16
}

func Plan(inventory model.Inventory, policy model.Policy) ([][]string, bool) {
	ctx := newContext(inventory, policy)
	all := uint16(1)<<len(ctx.targets) - 1
	initial := searchState{}
	minimum := (len(ctx.targets) + policy.MaxWaveSize - 1) / policy.MaxWaveSize

	for waveLimit := minimum; waveLimit <= len(ctx.targets); waveLimit++ {
		memo := make(map[depthState]memoResult)
		var solve func(searchState, int) memoResult
		solve = func(state searchState, wavesLeft int) memoResult {
			key := depthState{state: state, left: uint8(wavesLeft)}
			if saved, exists := memo[key]; exists {
				return saved
			}
			remaining := all &^ state.completed
			remainingCount := bitCount(remaining)
			if wavesLeft == 0 {
				answer := memoResult{possible: remaining == 0}
				memo[key] = answer
				return answer
			}
			if remainingCount < wavesLeft || remainingCount > wavesLeft*policy.MaxWaveSize {
				memo[key] = memoResult{}
				return memoResult{}
			}

			best := memoResult{}
			for _, mask := range ctx.candidates {
				if mask&remaining != mask {
					continue
				}
				afterCount := remainingCount - bitCount(mask)
				if afterCount < wavesLeft-1 || afterCount > (wavesLeft-1)*policy.MaxWaveSize {
					continue
				}
				facts := ctx.facts[mask]
				if facts.required&state.completed != facts.required || !ctx.cooldownAllows(facts.cooldownServices, state.cooldown) || !ctx.separationAllows(mask, state) || !ctx.rollingAllows(facts, state) {
					continue
				}
				next := ctx.advance(state, mask, facts.cooldownServices)
				suffix := solve(next, wavesLeft-1)
				if !suffix.possible {
					continue
				}
				candidateRisk := facts.risk + suffix.risk
				if !best.possible || candidateRisk < best.risk ||
					(candidateRisk == best.risk && ctx.lessMask(mask, best.first)) {
					best = memoResult{possible: true, risk: candidateRisk, first: mask}
				}
			}
			memo[key] = best
			return best
		}

		answer := solve(initial, waveLimit)
		if !answer.possible {
			continue
		}
		waves := make([][]string, 0, waveLimit)
		state := initial
		wavesLeft := waveLimit
		for wavesLeft > 0 {
			step := memo[depthState{state: state, left: uint8(wavesLeft)}]
			waves = append(waves, append([]string(nil), ctx.facts[step.first].names...))
			state = ctx.advance(state, step.first, ctx.facts[step.first].cooldownServices)
			wavesLeft--
		}
		return waves, true
	}
	return nil, false
}

func (ctx context) cooldownAllows(selected uint16, encoded uint32) bool {
	for index := range ctx.cooldownKeys {
		if selected&(uint16(1)<<index) != 0 && (encoded>>(2*index))&3 != 0 {
			return false
		}
	}
	return true
}

func (ctx context) nextCooldown(encoded uint32, selected uint16) uint32 {
	var next uint32
	for index, service := range ctx.cooldownKeys {
		value := int((encoded >> (2 * index)) & 3)
		if value > 0 {
			value--
		}
		if selected&(uint16(1)<<index) != 0 && ctx.policy.Cooldown[service] > value {
			value = ctx.policy.Cooldown[service]
		}
		next |= uint32(value) << (2 * index)
	}
	return next
}

func (ctx context) separationAllows(mask uint16, state searchState) bool {
	for _, rule := range ctx.separation {
		var earlier uint16
		if mask&rule.left != 0 && state.completed&rule.right != 0 {
			earlier = rule.right
		} else if mask&rule.right != 0 && state.completed&rule.left != 0 {
			earlier = rule.left
		}
		for index := 0; earlier != 0 && index < rule.gap; index++ {
			if state.recent[index]&earlier != 0 {
				return false
			}
		}
	}
	return true
}

func (ctx context) rollingAllows(facts maskFacts, state searchState) bool {
	for index, service := range ctx.rollingKeys {
		limit := ctx.policy.RollingLimits[service]
		count := int(facts.rollingCounts[index])
		for previous := 0; previous < limit.Window-1; previous++ {
			count += int(ctx.facts[state.recent[previous]].rollingCounts[index])
		}
		if count > limit.MaxUnavailable {
			return false
		}
	}
	return true
}

func (ctx context) advance(state searchState, mask uint16, selectedServices uint16) searchState {
	next := searchState{completed: state.completed | mask, cooldown: ctx.nextCooldown(state.cooldown, selectedServices)}
	if ctx.historyDepth > 0 {
		next.recent[0] = mask
		for index := 1; index < ctx.historyDepth; index++ {
			next.recent[index] = state.recent[index-1]
		}
	}
	return next
}
