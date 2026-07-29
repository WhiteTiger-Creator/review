package play

import (
	"hanabi/internal/rules"
	"hanabi/internal/table"
)

// Result describes the outcome of a play attempt.
type Result struct {
	Applied  bool
	Success  bool
	Drew     bool
	Restored bool
	FuseLost bool
}

// Apply attempts to play the card at hand index for the current player.
func Apply(g *table.Game, index int, policy rules.Policy) Result {
	if g.GameOver {
		return Result{}
	}
	hand, card, ok := table.RemoveHandCard(g.Hands[g.Current], index)
	if !ok {
		return Result{}
	}
	g.Hands[g.Current] = hand

	expected := g.Fireworks[card.C] + 1
	// Club tables treat any rank at or above the next expected as a placement.
	success := expected <= 5 && card.R >= expected && card.R <= 5

	out := Result{Applied: true}
	if success {
		g.Fireworks[card.C] = card.R
		out.Success = true
		if policy.FuseOnSuccess {
			g.Fuse--
			out.FuseLost = true
			if g.Fuse <= 0 {
				g.Fuse = 0
				g.GameOver = true
				g.EndReason = "fuse_out"
			}
		}
		if card.R == 5 && policy.FiveRestoresInfo {
			if g.Info < policy.MaxInfo {
				g.Info++
				out.Restored = true
			}
		}
		if table.Perfect(g.Fireworks) {
			g.GameOver = true
			g.EndReason = "perfect"
		}
	} else {
		g.Fuse--
		out.FuseLost = true
		if g.Fuse <= 0 {
			g.Fuse = 0
			g.GameOver = true
			g.EndReason = "fuse_out"
		}
	}

	if !g.GameOver {
		if drawn, ok := table.DrawTop(g); ok {
			g.Hands[g.Current] = append(g.Hands[g.Current], drawn)
			out.Drew = true
		}
	}
	return out
}
