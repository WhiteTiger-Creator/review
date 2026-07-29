// Package tiles handles the tile notation used by the hand log.
package tiles

import (
	"fmt"
	"sort"
	"strings"
)

// Count is the number of distinct tile kinds: 9 per suit plus 7 honours.
const Count = 34

// Wind and dragon indices.
const (
	East  = 27
	South = 28
	West  = 29
	North = 30
	White = 31
	Green = 32
	Red   = 33
)

// Terminals lists the 1 and 9 tiles of every suit.
var Terminals = []int{0, 8, 9, 17, 18, 26}

// Honours lists the four winds and three dragons.
var Honours = []int{East, South, West, North, White, Green, Red}

// Group is a parsed notation string: how many of each kind, plus how many of the
// tiles are red fives.
type Group struct {
	Counts [Count]int
	// Reds holds one entry per red five in the group, giving its tile index.
	Reds []int
}

// Total returns how many tiles the group holds.
func (g Group) Total() int {
	n := 0
	for _, c := range g.Counts {
		n += c
	}
	return n
}

// Indices lists the group's tiles in ascending order, with repeats.
func (g Group) Indices() []int {
	var out []int
	for tile, c := range g.Counts {
		for i := 0; i < c; i++ {
			out = append(out, tile)
		}
	}
	sort.Ints(out)
	return out
}

// Parse reads notation such as "123m456p789s11z", where digits are grouped by suit
// (m, p, s) or by honour (z, 1-7 for east, south, west, north, white, green, red) and
// the digit 0 stands for a red five of its suit.
func Parse(text string) (Group, error) {
	var g Group
	var pending []rune
	for _, r := range text {
		switch r {
		case 'm', 'p', 's', 'z':
			if len(pending) == 0 {
				return g, fmt.Errorf("suit %q without digits in %q", r, text)
			}
			for _, d := range pending {
				tile, red, err := index(d, r)
				if err != nil {
					return g, fmt.Errorf("%w in %q", err, text)
				}
				g.Counts[tile]++
				if red {
					g.Reds = append(g.Reds, tile)
				}
			}
			pending = pending[:0]
		default:
			if r < '0' || r > '9' {
				return g, fmt.Errorf("unexpected %q in %q", r, text)
			}
			pending = append(pending, r)
		}
	}
	if len(pending) > 0 {
		return g, fmt.Errorf("trailing digits in %q", text)
	}
	return g, nil
}

// ParseTile reads a single tile such as "5m", "1z" or the red five "0s".
func ParseTile(text string) (tile int, red bool, err error) {
	if len(text) != 2 {
		return 0, false, fmt.Errorf("bad tile %q", text)
	}
	return index(rune(text[0]), rune(text[1]))
}

func index(digit, suit rune) (int, bool, error) {
	if suit == 'z' {
		if digit < '1' || digit > '7' {
			return 0, false, fmt.Errorf("bad honour %c", digit)
		}
		return 27 + int(digit-'1'), false, nil
	}
	base := strings.IndexRune("mps", suit)
	if base < 0 {
		return 0, false, fmt.Errorf("bad suit %c", suit)
	}
	if digit == '0' {
		return base*9 + 4, true, nil
	}
	if digit < '1' || digit > '9' {
		return 0, false, fmt.Errorf("bad number %c", digit)
	}
	return base*9 + int(digit-'1'), false, nil
}

// Name renders a tile index back into notation, never as a red five.
func Name(tile int) string {
	if tile >= East {
		return fmt.Sprintf("%dz", tile-East+1)
	}
	return fmt.Sprintf("%d%c", tile%9+1, "mps"[tile/9])
}

// IsHonour reports whether the tile is a wind or a dragon.
func IsHonour(tile int) bool { return tile >= East }

// IsTerminal reports whether the tile is a 1 or a 9 of a suit.
func IsTerminal(tile int) bool { return !IsHonour(tile) && (tile%9 == 0 || tile%9 == 8) }

// Rank returns 0-8 for a suited tile and -1 for an honour.
func Rank(tile int) int {
	if IsHonour(tile) {
		return -1
	}
	return tile % 9
}

// Suit returns 0, 1 or 2 for man, pin and sou, and -1 for an honour.
func Suit(tile int) int {
	if IsHonour(tile) {
		return -1
	}
	return tile / 9
}
