package table

// Colors lists the five firework colors in championship order.
var Colors = []string{"R", "Y", "G", "B", "W"}

// Card is a single Hanabi card with color and rank.
type Card struct {
	C string `json:"c"`
	R int    `json:"r"`
}

// Move is one requested action from a scenario.
type Move struct {
	Type  string `json:"type"`
	To    int    `json:"to"`
	Kind  string `json:"kind"`
	Value string `json:"value"`
	Index int    `json:"index"`
}

// Game holds mutable table state for one scenario.
type Game struct {
	Players      int
	Hands        [][]Card
	Deck         []Card
	Info         int
	Fuse         int
	Fireworks    map[string]int
	Current      int
	FinalLeft    int
	DeckWasEmpty bool
	GameOver     bool
	EndReason    string
}

// CloneFireworks returns a copy of the firework map.
func CloneFireworks(src map[string]int) map[string]int {
	out := make(map[string]int, len(Colors))
	for _, c := range Colors {
		out[c] = src[c]
	}
	return out
}

// CloneHands deep-copies every hand.
func CloneHands(hands [][]Card) [][]Card {
	out := make([][]Card, len(hands))
	for i := range hands {
		out[i] = append([]Card(nil), hands[i]...)
	}
	return out
}

// CloneDeck copies the draw pile.
func CloneDeck(deck []Card) []Card {
	return append([]Card(nil), deck...)
}

// ScoreSum returns the championship score: sum of firework ranks.
func ScoreSum(fw map[string]int) int {
	total := 0
	for _, c := range Colors {
		total += fw[c]
	}
	return total
}

// Perfect reports whether every color stack is complete at rank 5.
func Perfect(fw map[string]int) bool {
	for _, c := range Colors {
		if fw[c] != 5 {
			return false
		}
	}
	return true
}

// DrawTop removes and returns the top deck card; ok is false when empty.
func DrawTop(g *Game) (Card, bool) {
	if len(g.Deck) == 0 {
		return Card{}, false
	}
	card := g.Deck[0]
	g.Deck = g.Deck[1:]
	if len(g.Deck) == 0 && !g.DeckWasEmpty {
		g.DeckWasEmpty = true
		// Club-night timing: counter equals player count (emptying action already counted).
		g.FinalLeft = g.Players
	}
	return card, true
}

// RemoveHandCard deletes index from a hand and returns the card.
func RemoveHandCard(hand []Card, index int) ([]Card, Card, bool) {
	if index < 0 || index >= len(hand) {
		return hand, Card{}, false
	}
	card := hand[index]
	out := append(append([]Card(nil), hand[:index]...), hand[index+1:]...)
	return out, card, true
}
