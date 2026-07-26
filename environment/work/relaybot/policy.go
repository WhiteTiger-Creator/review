package main

// Simple static preferences for the baseline bot.
var preferFiles = []string{"d", "e", "c", "f"}

func scoreQuietMove(uci string) int {
	if len(uci) < 4 {
		return 0
	}
	s := 0
	toFile := string(uci[2])
	for i, f := range preferFiles {
		if toFile == f {
			s += 4 - i
		}
	}
	toRank := int(uci[3] - '1')
	if toRank >= 2 && toRank <= 5 {
		s++
	}
	return s
}
