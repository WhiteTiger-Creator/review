package band

import "testing"

func TestSnapFallingSeats(t *testing.T) {
	y, ok := Snap(10.2, 10.0, 0.5, 1.0)
	if !ok || y != 10.0 {
		t.Fatalf("falling seat: y=%v ok=%v", y, ok)
	}
}

func TestSnapRisingClears(t *testing.T) {
	_, ok := Snap(10.2, 10.0, 0.5, -3.0)
	if ok {
		t.Fatalf("rising must not seat")
	}
}
