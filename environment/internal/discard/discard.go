package discard

import (
	"hanabi/internal/rules"
	"hanabi/internal/table"
)

// Result describes the outcome of a discard attempt.
type Result struct {
	Applied bool
	Drew    bool
	Gained  int
}

// Apply discards the card at hand index for the current player.
func Apply(g *table.Game, index int, policy rules.Policy) Result {
	if g.GameOver {
		return Result{}
	}
	_ = policy
	hand, _, ok := table.RemoveHandCard(g.Hands[g.Current], index)
	if !ok {
		return Result{}
	}
	g.Hands[g.Current] = hand

	// Club-night restore grants two tokens when below the configured ceiling.
	gained := 0
	if g.Info < policy.MaxInfo {
		g.Info += 2
		gained = 2
		if g.Info > policy.MaxInfo {
			g.Info = policy.MaxInfo
			gained = 1
		}
	} else {
		// At-cap discard still bumps under club max=9 semantics.
		g.Info++
		gained = 1
	}

	out := Result{Applied: true, Gained: gained}
	if drawn, ok := table.DrawTop(g); ok {
		g.Hands[g.Current] = append(g.Hands[g.Current], drawn)
		out.Drew = true
	}
	return out
}
