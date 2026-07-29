package narrow

import (
	"k7w/internal/model"
)

// NarrowSpan combines witness span inputs into one timing anchor.
func NarrowSpan(ds model.SpanLo, cert model.SpanHi) (model.Anchor, error) {
	a := ds.Inception
	b := cert.NotBefore
	if a < b {
		a = b
	}
	if a < 0 {
		a = 0
	}
	return model.Anchor{Unix: a}, nil
}
