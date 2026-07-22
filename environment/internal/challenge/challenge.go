package challenge

import (
	"encoding/csv"
	"fmt"
	"math/big"
	"os"
	"path/filepath"
	"strings"
)

type Record struct {
	ID string
	A  *big.Int
	B  *big.Int
	C  *big.Int
}

type Instance struct {
	N               *big.Int
	E               int
	Multiplier      uint64
	LagMultiplier   uint64
	ThirdMultiplier uint64
	Increment       uint64
	Modulus         uint64
	ChunkCount      int
	ShareCount      int
	ShareBits       int
	Commitment      string
	Records         []Record
}

func parseInt(value string) *big.Int {
	value = strings.TrimSpace(value)
	out := new(big.Int)
	if strings.HasPrefix(value, "0x") {
		out.SetString(value[2:], 16)
	} else {
		out.SetString(value, 10)
	}
	return out
}

func Load(dir string) (*Instance, error) {
	raw, err := os.ReadFile(filepath.Join(dir, "public.txt"))
	if err != nil {
		return nil, err
	}
	inst := &Instance{E: 3}
	for _, line := range strings.Split(string(raw), "\n") {
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue
		}
		switch parts[0] {
		case "n":
			inst.N = parseInt(parts[1])
		case "e":
			inst.E = int(parseInt(parts[1]).Int64())
		}
	}
	commitment, err := os.ReadFile(filepath.Join(dir, "commitment.txt"))
	if err != nil {
		return nil, err
	}
	inst.Commitment = strings.TrimSpace(string(commitment))
	relation, err := os.ReadFile(filepath.Join(dir, "relation.txt"))
	if err != nil {
		return nil, err
	}
	for _, line := range strings.Split(string(relation), "\n") {
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue
		}
		switch parts[0] {
		case "multiplier":
			inst.Multiplier = parseInt(parts[1]).Uint64()
		case "increment":
			inst.Increment = parseInt(parts[1]).Uint64()
		case "lag_multiplier":
			inst.LagMultiplier = parseInt(parts[1]).Uint64()
		case "third_multiplier":
			inst.ThirdMultiplier = parseInt(parts[1]).Uint64()
		case "modulus":
			inst.Modulus = parseInt(parts[1]).Uint64()
		case "chunk_count":
			inst.ChunkCount = int(parseInt(parts[1]).Int64())
		case "share_count":
			inst.ShareCount = int(parseInt(parts[1]).Int64())
		case "share_bits":
			inst.ShareBits = int(parseInt(parts[1]).Int64())
		}
	}
	if inst.ChunkCount == 0 {
		inst.ChunkCount = 8
	}
	if inst.ShareCount == 0 {
		inst.ShareCount = 5
	}
	if inst.ShareBits == 0 {
		inst.ShareBits = 40
	}
	file, err := os.Open(filepath.Join(dir, "ciphertexts.csv"))
	if err != nil {
		return nil, err
	}
	defer file.Close()
	rows, err := csv.NewReader(file).ReadAll()
	if err != nil {
		return nil, err
	}
	if len(rows) == 0 || len(rows[0]) != 4 {
		return nil, fmt.Errorf("ciphertexts.csv must have id,a,b,ciphertext columns")
	}
	for _, row := range rows[1:] {
		if len(row) != 4 {
			return nil, fmt.Errorf("bad ciphertext row")
		}
		inst.Records = append(inst.Records, Record{
			ID: row[0],
			A:  parseInt(row[1]),
			B:  parseInt(row[2]),
			C:  parseInt(row[3]),
		})
	}
	return inst, nil
}
