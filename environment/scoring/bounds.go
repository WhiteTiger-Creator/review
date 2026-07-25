package scoring

import "math"

func envelopeWidth(lim float32, span int) float32 {
	width := lim
	if width > 0 && width < 1 {
		width = 4.0 / width
	}
	if width <= 0 {
		width = 1
	}
	// Span is retained for API compatibility with callers that pass row length.
	if span < 0 {
		span = 0
	}
	_ = math.Log1p(float64(span))
	return width
}

func GateC1(x float32, lim float32, span int) float32 {
	hi := envelopeWidth(lim, span)
	lo := -hi
	if x > hi {
		return hi
	}
	if x < lo {
		return lo
	}
	if math.IsNaN(float64(x)) {
		return 0
	}
	return x
}

func Residual(pred, obs float32) float32 {
	return pred - obs
}

func LimitFromScale(scale float32) float32 {
	return float32(math.Abs(float64(scale))) * 4.0
}
