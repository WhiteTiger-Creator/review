package tiles_test

import (
	"testing"

	"scoreboard/handsettle/internal/tiles"
)

func TestParseGroups(t *testing.T) {
	group, err := tiles.Parse("123m0p55z")
	if err != nil {
		t.Fatal(err)
	}
	if group.Total() != 6 {
		t.Fatalf("total = %d, want 6", group.Total())
	}
	if group.Counts[0] != 1 || group.Counts[2] != 1 {
		t.Errorf("characters 1 and 3 missing: %v", group.Counts[:9])
	}
	if group.Counts[13] != 1 {
		t.Errorf("red five of circles should land on the ordinary five")
	}
	if len(group.Reds) != 1 || group.Reds[0] != 13 {
		t.Errorf("reds = %v, want the five of circles", group.Reds)
	}
	if group.Counts[tiles.White] != 2 {
		t.Errorf("white dragons = %d, want 2", group.Counts[tiles.White])
	}
}

func TestNameRoundTrip(t *testing.T) {
	for _, text := range []string{"1m", "9p", "5s", "1z", "7z"} {
		tile, _, err := tiles.ParseTile(text)
		if err != nil {
			t.Fatalf("%s: %v", text, err)
		}
		if got := tiles.Name(tile); got != text {
			t.Errorf("Name(%d) = %s, want %s", tile, got, text)
		}
	}
}

func TestRejectsJunk(t *testing.T) {
	for _, text := range []string{"1", "m", "8z", "1x", "12"} {
		if _, err := tiles.Parse(text); err == nil {
			t.Errorf("Parse(%q) should fail", text)
		}
	}
}
