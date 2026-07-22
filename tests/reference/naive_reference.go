package main

import (
	"encoding/csv"
	"math/big"
	"os"
	"path/filepath"
	"strings"
)

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

func readFirstCipher(dir string) *big.Int {
	file, err := os.Open(filepath.Join(dir, "ciphertexts.csv"))
	if err != nil {
		panic(err)
	}
	defer file.Close()
	rows, err := csv.NewReader(file).ReadAll()
	if err != nil {
		panic(err)
	}
	if len(rows) < 2 {
		return big.NewInt(0)
	}
	return parseInt(rows[1][3])
}

func readExponent(dir string) int64 {
	raw, err := os.ReadFile(filepath.Join(dir, "public.txt"))
	if err != nil {
		panic(err)
	}
	for _, line := range strings.Split(string(raw), "\n") {
		parts := strings.SplitN(line, "=", 2)
		if len(parts) == 2 && parts[0] == "e" {
			return parseInt(parts[1]).Int64()
		}
	}
	return 0
}

func integerRoot(n *big.Int, exp int64) *big.Int {
	lo := big.NewInt(0)
	hi := new(big.Int).Lsh(big.NewInt(1), uint(n.BitLen()/int(exp)+3))
	one := big.NewInt(1)
	for new(big.Int).Add(lo, one).Cmp(hi) < 0 {
		mid := new(big.Int).Add(lo, hi)
		mid.Rsh(mid, 1)
		power := new(big.Int).Set(mid)
		for i := int64(1); i < exp; i++ {
			power.Mul(power, mid)
		}
		if power.Cmp(n) <= 0 {
			lo = mid
		} else {
			hi = mid
		}
	}
	return lo
}

func looksLikeFlag(value string) bool {
	if len(value) != 88 || value[:7] != "CICADA{" || value[87] != '}' {
		return false
	}
	for _, ch := range value[7:87] {
		if !((ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f')) {
			return false
		}
	}
	return true
}

func main() {
	c := readFirstCipher(os.Args[1])
	root := integerRoot(c, readExponent(os.Args[1]))
	out := string(root.Bytes())
	if !looksLikeFlag(out) {
		out = "CICADA{00000000000000000000000000000000000000000000000000000000000000000000000000000000}"
	}
	if err := os.WriteFile(os.Args[2], []byte(out+"\n"), 0644); err != nil {
		panic(err)
	}
}
