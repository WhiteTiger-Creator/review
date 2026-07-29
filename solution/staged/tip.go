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
	tip := -1
	seen := 0
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
		seen++
		if rec.Tomb {
			continue
		}
		if rec.Gen < 0 {
			continue
		}
		if rec.Gen > tip {
			tip = rec.Gen
		}
	}
	if err := sc.Err(); err != nil {
		return 0, err
	}
	if seen == 0 || tip < 0 {
		return 0, nil
	}
	return tip, nil
}

func Run() (int, error) {
	return tip_q(ledgerPath)
}
