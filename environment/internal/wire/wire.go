package wire

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"errors"
	"k7w/internal/model"
)

func BodyOf(frame []byte) ([]byte, error) {
	if len(frame) < 8 || string(frame[:4]) != model.FrameMagic {
		return nil, errors.New("bad frame magic")
	}
	blen := int(binary.BigEndian.Uint16(frame[6:8]))
	if 8+blen > len(frame) {
		return nil, errors.New("truncated frame")
	}
	return frame[8 : 8+blen], nil
}

// CanonicalTLV strips 0x00 filler TLVs at every nesting depth.
func CanonicalTLV(body []byte) []byte {
	out := make([]byte, 0, len(body))
	off := 0
	for off+3 <= len(body) {
		tag := body[off]
		ln := int(binary.BigEndian.Uint16(body[off+1 : off+3]))
		if off+3+ln > len(body) {
			break
		}
		val := body[off+3 : off+3+ln]
		off += 3 + ln
		if tag == model.TagFiller {
			continue
		}
		if tag >= model.TagNest {
			inner := CanonicalTLV(val)
			out = append(out, tag)
			var l [2]byte
			binary.BigEndian.PutUint16(l[:], uint16(len(inner)))
			out = append(out, l[:]...)
			out = append(out, inner...)
			continue
		}
		out = append(out, tag)
		var l [2]byte
		binary.BigEndian.PutUint16(l[:], uint16(ln))
		out = append(out, l[:]...)
		out = append(out, val...)
	}
	return out
}

func ParseChunks(body []byte) ([]model.Chunk, error) {
	var chunks []model.Chunk
	off := 0
	for off+3 <= len(body) {
		tag := body[off]
		ln := int(binary.BigEndian.Uint16(body[off+1 : off+3]))
		if off+3+ln > len(body) {
			return nil, errors.New("bad tlv")
		}
		val := append([]byte(nil), body[off+3:off+3+ln]...)
		off += 3 + ln
		if tag == model.TagFiller {
			continue
		}
		chunks = append(chunks, model.Chunk{Tag: tag, Value: val})
	}
	return chunks, nil
}

func CanonStamp(frame []byte) (string, error) {
	body, err := BodyOf(frame)
	if err != nil {
		return "", err
	}
	can := CanonicalTLV(body)
	h := sha256.Sum256(can)
	return hex.EncodeToString(h[:]), nil
}
