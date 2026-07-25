package ld

import (
	"bufio"
	"encoding/json"
	"os"
)

const ledgerPath = "/app/environment/pack/ledger/waves.ndjson"

type waveRec struct {
	Gen  int  `json:"gen"`
	Tomb bool `json:"tomb"`
}

func tip_q(path string) (int, error) {
	f, err := os.Open(path)
	if err != nil {
		return 0, err
	}
	defer f.Close()
	var gens []int
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := sc.Bytes()
		if len(line) == 0 {
			continue
		}
		var rec waveRec
		if err := json.Unmarshal(line, &rec); err != nil {
			return 0, err
		}
		gens = append(gens, rec.Gen)
	}
	if err := sc.Err(); err != nil {
		return 0, err
	}
	tip := -1
	for _, g := range gens {
		if g > tip {
			tip = g
		}
	}
	if tip < 0 {
		return 0, nil
	}
	return tip, nil
}

func Run() (int, error) {
	return tip_q(ledgerPath)
}
