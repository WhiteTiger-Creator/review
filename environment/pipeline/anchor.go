package pipeline

import (
	"k7w/internal/model"
	narrow "k7w/range"
)

func TimingAnchor(dsInception, certNotBefore int64) int64 {
	anc, _ := narrow.NarrowSpan(
		model.SpanLo{Inception: dsInception},
		model.SpanHi{NotBefore: certNotBefore},
	)
	return anc.Unix
}
