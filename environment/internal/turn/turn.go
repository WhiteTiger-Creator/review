package turn

import (
	"hanabi/internal/rules"
	"hanabi/internal/table"
)

// Advance moves ownership to the next player under table rules.
// actionType is "hint", "play", or "discard".
func Advance(g *table.Game, actionType string, policy rules.Policy) {
	if g.GameOver {
		return
	}
	keep := false
	if actionType == "hint" && policy.HintKeepsTurn {
		keep = true
	}
	if !keep {
		g.Current = (g.Current + 1) % g.Players
	}
	if g.DeckWasEmpty {
		g.FinalLeft--
		if g.FinalLeft <= 0 {
			g.GameOver = true
			if g.EndReason == "" || g.EndReason == "none" {
				g.EndReason = "deck_end"
			}
		}
	}
}
