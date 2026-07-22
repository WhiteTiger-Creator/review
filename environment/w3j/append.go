package w3j

import (
	"encoding/json"
	"os"
	"sort"
	"strings"
)

func fn_w3(lines []RawLine, walPath string) ([]Frame, error) {
	var epoch uint64
	type key struct {
		pkg, dep string
		arm      byte
	}
	best := map[key]Frame{}
	order := []key{}
	for _, ln := range lines {
		raw, err := ParseLoose(ln.Bytes)
		if err != nil {
			return nil, err
		}
		fr := Frame{ArmTag: ln.ArmTag}
		if v, ok := raw["pkg"].(string); ok {
			fr.Pkg = v
		}
		if v, ok := raw["dep"].(string); ok {
			fr.Dep = v
		}
		if v, ok := raw["lo"].(string); ok {
			fr.Lo = v
		}
		if v, ok := raw["hi"].(string); ok {
			fr.Hi = v
		}
		if v, ok := raw["pre_tok"].(string); ok {
			fr.PreTok = v
		}
		if v, ok := raw["lift"].(bool); ok {
			fr.Lift = v
		}
		if v, ok := raw["act_tok"].(string); ok {
			fr.ActTok = v
		}
		if v, ok := raw["seq"].(float64); ok {
			fr.Seq = int(v)
		}
		switch ln.ArmTag {
		case 'a':
			if fr.PreTok == "allow" {
				fr.PreTok = ""
			}
		case 'b':
			fr.Lo = StripPreToken(fr.Lo)
			fr.Hi = StripPreToken(fr.Hi)
			if fr.PreTok == "" {
				fr.PreTok = "allow"
			}
		}
		epoch++
		fr.Epoch = epoch
		fr.CRC = SealCRC(fr)
		k := key{fr.Pkg, fr.Dep, fr.ArmTag}
		if prev, ok := best[k]; !ok {
			best[k] = fr
			order = append(order, k)
		} else if fr.Seq < prev.Seq || (fr.Seq == prev.Seq && fr.Epoch < prev.Epoch) {
			best[k] = fr
		}
	}

	if b, err := os.ReadFile(walPath); err == nil {
		type walRow struct {
			fr Frame
			k  key
		}
		var prior []walRow
		for _, line := range strings.Split(string(b), "\n") {
			line = strings.TrimSpace(line)
			if line == "" {
				continue
			}
			var fr Frame
			if json.Unmarshal([]byte(line), &fr) != nil {
				continue
			}
			prior = append(prior, walRow{fr: fr, k: key{fr.Pkg, fr.Dep, fr.ArmTag}})
		}
		sort.SliceStable(prior, func(i, j int) bool {
			if prior[i].fr.Seq != prior[j].fr.Seq {
				return prior[i].fr.Seq < prior[j].fr.Seq
			}
			return prior[i].fr.Epoch < prior[j].fr.Epoch
		})
		for _, row := range prior {
			fr := row.fr
			k := row.k
			if prev, ok := best[k]; !ok || fr.Seq >= prev.Seq {
				best[k] = fr
				if !ok {
					order = append(order, k)
				}
			}
		}
	}

	out := make([]Frame, 0, len(order))
	for _, k := range order {
		if fr, ok := best[k]; ok {
			out = append(out, fr)
		}
	}
	if err := writeWAL(walPath, out); err != nil {
		return nil, err
	}
	return out, nil
}

func FnW3(lines []RawLine, walPath string) ([]Frame, error) {
	return fn_w3(lines, walPath)
}
