package main

import (
	"encoding/binary"
	"os"
	"path/filepath"

	"k7w/internal/model"
)

func tlv(tag byte, val []byte) []byte {
	out := []byte{tag}
	var l [2]byte
	binary.BigEndian.PutUint16(l[:], uint16(len(val)))
	out = append(out, l[:]...)
	out = append(out, val...)
	return out
}

func frame(body []byte) []byte {
	out := append([]byte(model.FrameMagic), 0, 0)
	var bl [2]byte
	binary.BigEndian.PutUint16(bl[:], uint16(len(body)))
	out = append(out, bl[:]...)
	out = append(out, body...)
	return out
}

func writePack(path string, entries map[string][]byte) error {
	var buf []byte
	buf = append(buf, []byte("K7PK")...)
	var c [4]byte
	binary.BigEndian.PutUint32(c[:], uint32(len(entries)))
	buf = append(buf, c[:]...)
	for name, blob := range entries {
		nb := []byte(name)
		var nl [4]byte
		binary.BigEndian.PutUint32(nl[:], uint32(len(nb)))
		buf = append(buf, nl[:]...)
		buf = append(buf, nb...)
		var bl [4]byte
		binary.BigEndian.PutUint32(bl[:], uint32(len(blob)))
		buf = append(buf, bl[:]...)
		buf = append(buf, blob...)
	}
	return os.WriteFile(path, buf, 0o644)
}

func main() {
	root := filepath.Join("bundle", "k7")
	_ = os.MkdirAll(root, 0o755)
	bodyA := tlv(model.TagAltSSH, []byte("host-a.example"))
	bodyA = append(bodyA, tlv(model.TagUsage, []byte{0x01})...)
	bodyB := tlv(model.TagAltDNS, []byte("dns.example"))
	bodyB = append(bodyB, tlv(model.TagAltSSH, []byte("host-b.example"))...)
	bodyB = append(bodyB, tlv(model.TagUsage, []byte{0x01})...)
	bodyG := tlv(model.TagAltDNS, []byte("gamma-dns.example"))
	bodyG = append(bodyG, tlv(model.TagAltSSH, []byte("gamma-ssh.example"))...)
	bodyG = append(bodyG, tlv(model.TagUsage, []byte{0x02})...)
	pad := append([]byte(nil), bodyB...)
	pad = append(pad, tlv(model.TagFiller, []byte{0x00, 0x00})...)
	entries := map[string][]byte{
		"alpha": frame(bodyA),
		"beta":  frame(bodyB),
		"gamma": frame(bodyG),
	}
	_ = writePack(filepath.Join(root, "base.k7"), entries)
	_ = os.WriteFile(filepath.Join(root, "var089.pad"), frame(pad), 0o644)
}
