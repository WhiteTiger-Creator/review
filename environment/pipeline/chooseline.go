package pipeline

import (
	"k7w/internal/model"
	"k7w/internal/wire"
	"k7w/slot"
)

func ScopeFromFrame(frame []byte, prof model.Tmpl) (string, model.AltPick, error) {
	body, err := wire.BodyOf(frame)
	if err != nil {
		return "", model.AltPick{}, err
	}
	chunks, err := wire.ParseChunks(wire.CanonicalTLV(body))
	if err != nil {
		return "", model.AltPick{}, err
	}
	pick, err := slot.ChooseAlt(chunks, prof)
	if err != nil {
		return "", model.AltPick{}, err
	}
	scope := "ok"
	if pick.Kind == model.TagAltSSH {
		scope = "ssh"
	}
	if pick.Kind == model.TagAltDNS {
		scope = "dns"
	}
	return scope, pick, nil
}
