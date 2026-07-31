package feed

import "testing"

func TestAtBounds(t *testing.T) {
	if At([]int{1, 0, 1}, 1) {
		t.Fatal("expected false")
	}
	if !At([]int{1, 0, 1}, 2) {
		t.Fatal("expected true")
	}
	if At([]int{1}, 9) {
		t.Fatal("oob")
	}
}
