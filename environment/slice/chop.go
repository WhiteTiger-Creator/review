package slice

import (
	"k7w/internal/model"
	"k7w/internal/wire"
)

// ChopSegment consumes one frame and records the first structural chunk.
func ChopSegment(buf []byte, out *model.Chunk) (int, error) {
	body, err := wire.BodyOf(buf)
	if err != nil {
		return 0, err
	}
	can := wire.CanonicalTLV(body)
	chunks, err := wire.ParseChunks(can)
	if err != nil {
		return 0, err
	}
	if len(chunks) == 0 {
		return len(buf), nil
	}
	*out = chunks[0]
	return len(buf), nil
}

// CanonDigest returns a stamp for the frame body.
func CanonDigest(frame []byte) (string, error) {
	body, err := wire.BodyOf(frame)
	if err != nil {
		return "", err
	}
	return wire.RawStamp(body)
}
