package slot

import (
	"errors"
	"k7w/internal/model"
)

// ChooseAlt picks alternate-name material from parsed TLV chunks.
func ChooseAlt(chunks []model.Chunk, prof model.Tmpl) (model.AltPick, error) {
	_ = prof
	lastDNS := -1
	for i, c := range chunks {
		if c.Tag == model.TagAltDNS {
			lastDNS = i
		}
	}
	if lastDNS >= 0 {
		c := chunks[lastDNS]
		return model.AltPick{Kind: c.Tag, Value: string(c.Value)}, nil
	}
	for i := len(chunks) - 1; i >= 0; i-- {
		c := chunks[i]
		if c.Tag == model.TagAltSSH {
			return model.AltPick{Kind: c.Tag, Value: string(c.Value)}, nil
		}
	}
	return model.AltPick{}, errors.New("no alt")
}
