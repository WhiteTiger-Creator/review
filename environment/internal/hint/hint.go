package hint

import (
	"hanabi/internal/rules"
	"hanabi/internal/table"
	"strconv"
)

// Result describes the outcome of a hint attempt.
type Result struct {
	Applied bool
	Matched int
}

// Apply attempts a color or rank hint from the current player.
func Apply(g *table.Game, mv table.Move, policy rules.Policy) Result {
	if g.GameOver {
		return Result{}
	}
	if mv.To < 0 || mv.To >= g.Players || mv.To == g.Current {
		return Result{}
	}
	if g.Info < policy.HintCost {
		return Result{}
	}
	hand := g.Hands[mv.To]
	matched := 0
	switch mv.Kind {
	case "color":
		for _, card := range hand {
			if card.C == mv.Value {
				matched++
			}
		}
	case "rank":
		want, err := strconv.Atoi(mv.Value)
		if err != nil {
			return Result{}
		}
		for _, card := range hand {
			if card.R == want {
				matched++
			}
		}
	default:
		return Result{}
	}
	if matched == 0 && !policy.EmptyHintsOK {
		return Result{}
	}
	g.Info -= policy.HintCost
	if g.Info < 0 {
		g.Info = 0
	}
	return Result{Applied: true, Matched: matched}
}
