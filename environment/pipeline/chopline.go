package pipeline

import (
	"k7w/internal/model"
	"k7w/slice"
)

func FrameStamp(frame []byte) (string, error) {
	var ch model.Chunk
	if _, err := slice.ChopSegment(frame, &ch); err != nil {
		return "", err
	}
	return slice.CanonDigest(frame)
}
