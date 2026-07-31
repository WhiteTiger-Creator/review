package feed

import "testing"

func TestHoldEligible(t *testing.T) {
	ns, hop := Hold(3, false, true, 4)
	if !hop || ns != 0 {
		t.Fatalf("eligible hop: ns=%d hop=%v", ns, hop)
	}
}
