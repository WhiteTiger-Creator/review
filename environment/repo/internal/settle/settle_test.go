package settle_test

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"testing"

	"scoreboard/handsettle/internal/settle"
	"scoreboard/handsettle/internal/table"
)

// TestExamples replays the worked hands under /app/examples.
func TestExamples(t *testing.T) {
	dir := filepath.Join("..", "..", "examples")
	hands := read[table.Hand](t, filepath.Join(dir, "hands.json"))
	want := read[table.Result](t, filepath.Join(dir, "expected.json"))
	if len(hands) == 0 || len(hands) != len(want) {
		t.Fatalf("expected a hand log and a report of the same length, got %d and %d",
			len(hands), len(want))
	}
	for i, hand := range hands {
		expected := want[i]
		t.Run(hand.ID, func(t *testing.T) {
			got, err := settle.Settle(hand)
			if err != nil {
				t.Fatalf("settle: %v", err)
			}
			if got.Scored != expected.Scored {
				t.Fatalf("scored = %v, want %v", got.Scored, expected.Scored)
			}
			if !expected.Scored {
				return
			}
			if got.Han != expected.Han || got.Fu != expected.Fu {
				t.Errorf("han/fu = %d/%d, want %d/%d", got.Han, got.Fu, expected.Han, expected.Fu)
			}
			gotYaku := append([]string(nil), got.Yaku...)
			wantYaku := append([]string(nil), expected.Yaku...)
			sort.Strings(gotYaku)
			sort.Strings(wantYaku)
			if !reflect.DeepEqual(gotYaku, wantYaku) {
				t.Errorf("yaku = %v, want %v", gotYaku, wantYaku)
			}
			if got.Payment == nil || expected.Payment == nil {
				if (got.Payment == nil) != (expected.Payment == nil) {
					t.Errorf("payment = %v, want %v", got.Payment, expected.Payment)
				}
				return
			}
			if *got.Payment != *expected.Payment {
				t.Errorf("payment = %+v, want %+v", *got.Payment, *expected.Payment)
			}
		})
	}
}

func read[T any](t *testing.T, path string) []T {
	t.Helper()
	blob, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var out []T
	if err := json.Unmarshal(blob, &out); err != nil {
		t.Fatal(err)
	}
	return out
}
