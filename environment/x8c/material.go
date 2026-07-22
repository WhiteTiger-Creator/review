package x8c

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"sort"

	"depctrl/w3j"
)

// FingerprintFrames builds a stable digest over sealed frames for cache keys.
func FingerprintFrames(frames []w3j.Frame) string {
	type row struct {
		Pkg, Dep, Lo, Hi, PreTok, ActTok string
		Lift                             bool
		Seq                              int
		Arm                              byte
	}
	rows := make([]row, 0, len(frames))
	for _, f := range frames {
		rows = append(rows, row{
			Pkg: f.Pkg, Dep: f.Dep, Lo: f.Lo, Hi: f.Hi, PreTok: f.PreTok,
			ActTok: f.ActTok, Lift: f.Lift, Seq: f.Seq, Arm: f.ArmTag,
		})
	}
	sort.Slice(rows, func(i, j int) bool {
		ai := fmt.Sprintf("%s|%s|%d|%c", rows[i].Pkg, rows[i].Dep, rows[i].Seq, rows[i].Arm)
		aj := fmt.Sprintf("%s|%s|%d|%c", rows[j].Pkg, rows[j].Dep, rows[j].Seq, rows[j].Arm)
		return ai < aj
	})
	b, _ := json.Marshal(rows)
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

func HashBytes(parts ...[]byte) string {
	h := sha256.New()
	for _, p := range parts {
		h.Write(p)
		h.Write([]byte{0})
	}
	return hex.EncodeToString(h.Sum(nil))
}
