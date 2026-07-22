#!/usr/bin/env bash
set -euo pipefail

cd /app
cat > /app/internal/attack/attack.go <<'GO'
package attack

import (
	"cicada/recovery/internal/challenge"
	"cicada/recovery/internal/format"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"math/big"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

type poly []*big.Int

var leakedFactor *big.Int

func norm(x, n *big.Int) *big.Int {
	out := new(big.Int).Mod(x, n)
	if out.Sign() < 0 {
		out.Add(out, n)
	}
	return out
}

func rememberFactor(value, n *big.Int) {
	g := new(big.Int).GCD(nil, nil, norm(value, n), n)
	if g.Sign() > 0 && g.Cmp(big.NewInt(1)) > 0 && g.Cmp(n) < 0 {
		leakedFactor = new(big.Int).Set(g)
	}
}

func trim(p poly) poly {
	i := len(p) - 1
	for i > 0 && p[i].Sign() == 0 {
		i--
	}
	return p[:i+1]
}

func clone(p poly) poly {
	out := make(poly, len(p))
	for i := range p {
		out[i] = new(big.Int).Set(p[i])
	}
	return out
}

func sub(a, b poly, n *big.Int) poly {
	size := len(a)
	if len(b) > size {
		size = len(b)
	}
	out := make(poly, size)
	for i := 0; i < size; i++ {
		av := big.NewInt(0)
		bv := big.NewInt(0)
		if i < len(a) {
			av = a[i]
		}
		if i < len(b) {
			bv = b[i]
		}
		out[i] = norm(new(big.Int).Sub(av, bv), n)
	}
	return trim(out)
}

func mulScalarShift(p poly, scalar *big.Int, shift int, n *big.Int) poly {
	out := make(poly, len(p)+shift)
	for i := range out {
		out[i] = big.NewInt(0)
	}
	for i := range p {
		out[i+shift] = norm(new(big.Int).Mul(p[i], scalar), n)
	}
	return trim(out)
}

func monic(p poly, n *big.Int) poly {
	p = trim(p)
	inv := new(big.Int).ModInverse(p[len(p)-1], n)
	if inv == nil {
		rememberFactor(p[len(p)-1], n)
		return p
	}
	out := make(poly, len(p))
	for i := range p {
		out[i] = norm(new(big.Int).Mul(p[i], inv), n)
	}
	return trim(out)
}

func rem(a, b poly, n *big.Int) poly {
	r := clone(a)
	b = monic(b, n)
	if leakedFactor != nil {
		return poly{big.NewInt(0)}
	}
	for len(r) >= len(b) && !(len(r) == 1 && r[0].Sign() == 0) {
		coeff := new(big.Int).Set(r[len(r)-1])
		shift := len(r) - len(b)
		r = sub(r, mulScalarShift(b, coeff, shift, n), n)
	}
	return trim(r)
}

func gcdPoly(a, b poly, n *big.Int) poly {
	a = trim(a)
	b = trim(b)
	for !(len(b) == 1 && b[0].Sign() == 0) {
		a, b = b, rem(a, b, n)
	}
	return monic(a, n)
}

func polynomialFor(rec challenge.Record, exponent int, n *big.Int) poly {
	out := make(poly, exponent+1)
	for i := range out {
		binom := new(big.Int).Binomial(int64(exponent), int64(i))
		aPow := new(big.Int).Exp(rec.A, big.NewInt(int64(i)), nil)
		bPow := new(big.Int).Exp(rec.B, big.NewInt(int64(exponent-i)), nil)
		coeff := new(big.Int).Mul(binom, aPow)
		coeff.Mul(coeff, bPow)
		out[i] = norm(coeff, n)
	}
	out[0] = norm(new(big.Int).Sub(out[0], rec.C), n)
	return trim(out)
}

type shareKey struct {
	index int
	share int
}

func chunkCandidates(candidates map[shareKey]map[uint64]bool, index int, shareCount int) map[uint64]bool {
	keys := make([]shareKey, 0, shareCount)
	values := map[shareKey][]uint64{}
	for share := 0; share < shareCount; share++ {
		key := shareKey{index: index, share: share}
		keys = append(keys, key)
		for value := range candidates[key] {
			values[key] = append(values[key], value)
		}
		sort.Slice(values[key], func(i, j int) bool { return values[key][i] < values[key][j] })
		if len(values[key]) == 0 {
			return map[uint64]bool{}
		}
	}
	out := map[uint64]bool{}
	var search func(int, uint64)
	search = func(position int, combined uint64) {
		if position == len(keys) {
			out[combined] = true
			return
		}
		key := keys[position]
		for _, value := range values[key] {
			search(position+1, combined^value)
		}
	}
	search(0, 0)
	return out
}

func committedFlag(inst *challenge.Instance, candidates map[shareKey]map[uint64]bool) string {
	chunks := make([]map[uint64]bool, inst.ChunkCount)
	for index := range chunks {
		chunks[index] = chunkCandidates(candidates, index, inst.ShareCount)
		if len(chunks[index]) == 0 {
			return ""
		}
	}
	if inst.Modulus == 0 || inst.ChunkCount < 3 || inst.ShareBits <= 0 {
		return ""
	}
	mask40 := inst.Modulus - 1
	width := (inst.ShareBits + 3) / 4
	for first := range chunks[0] {
		for second := range chunks[1] {
			for third := range chunks[2] {
				sequence := []uint64{first, second, third}
				valid := true
				for index := 3; index < len(chunks); index++ {
					value := (inst.Multiplier*sequence[index-1] + inst.LagMultiplier*sequence[index-2] + inst.ThirdMultiplier*sequence[index-3] + inst.Increment) & mask40
					if !chunks[index][value] {
						valid = false
						break
					}
					sequence = append(sequence, value)
				}
				if !valid {
					continue
				}
				body := ""
				for _, chunk := range sequence {
					body += fmt.Sprintf("%0*x", width, chunk)
				}
				candidate := "CICADA{" + body + "}"
				digest := sha256.Sum256([]byte(candidate))
				if format.LooksLikeFlag(candidate) && hex.EncodeToString(digest[:]) == inst.Commitment {
					return candidate
				}
			}
		}
	}
	return ""
}

func addCandidate(inst *challenge.Instance, candidates map[shareKey]map[uint64]bool, fragmentRe *regexp.Regexp, text string, width int) bool {
	parts := fragmentRe.FindStringSubmatch(text)
	if len(parts) != 4 {
		return false
	}
	index, err := strconv.Atoi(parts[1])
	share, shareErr := strconv.Atoi(parts[2])
	value, valueErr := strconv.ParseUint(parts[3], 16, inst.ShareBits)
	if err != nil || shareErr != nil || valueErr != nil {
		return false
	}
	if index < 0 || index >= inst.ChunkCount || share < 0 || share >= inst.ShareCount || len(parts[3]) != width {
		return false
	}
	key := shareKey{index: index, share: share}
	if candidates[key] == nil {
		candidates[key] = map[uint64]bool{}
	}
	candidates[key][value] = true
	return true
}

func decryptWithFactor(inst *challenge.Instance, factor *big.Int, fragmentRe *regexp.Regexp, width int) string {
	if factor == nil || factor.Sign() == 0 {
		return ""
	}
	q := new(big.Int).Div(new(big.Int).Set(inst.N), factor)
	if new(big.Int).Mul(factor, q).Cmp(inst.N) != 0 {
		return ""
	}
	one := big.NewInt(1)
	phi := new(big.Int).Mul(new(big.Int).Sub(factor, one), new(big.Int).Sub(q, one))
	d := new(big.Int).ModInverse(big.NewInt(int64(inst.E)), phi)
	if d == nil {
		return ""
	}
	candidates := map[shareKey]map[uint64]bool{}
	for _, rec := range inst.Records {
		transformed := new(big.Int).Exp(rec.C, d, inst.N)
		invA := new(big.Int).ModInverse(rec.A, inst.N)
		if invA == nil {
			continue
		}
		m := norm(new(big.Int).Mul(new(big.Int).Sub(transformed, rec.B), invA), inst.N)
		addCandidate(inst, candidates, fragmentRe, string(m.Bytes()), width)
	}
	return committedFlag(inst, candidates)
}

func Recover(inst *challenge.Instance) string {
	leakedFactor = nil
	polys := make([]poly, len(inst.Records))
	for i, rec := range inst.Records {
		polys[i] = polynomialFor(rec, inst.E, inst.N)
	}
	width := (inst.ShareBits + 3) / 4
	fragmentRe := regexp.MustCompile(`^frag([0-9]+)\.([0-9]+):([0-9a-f]+)$`)
	candidates := map[shareKey]map[uint64]bool{}
	neededKeys := inst.ChunkCount * inst.ShareCount
	for i := 0; i < len(polys); i++ {
		for j := i + 1; j < len(polys); j++ {
			d := gcdPoly(polys[i], polys[j], inst.N)
			if leakedFactor != nil {
				if candidate := decryptWithFactor(inst, leakedFactor, fragmentRe, width); candidate != "" {
					return candidate
				}
				leakedFactor = nil
			}
			if len(d) != 2 {
				continue
			}
			m := norm(new(big.Int).Neg(d[0]), inst.N)
			if addCandidate(inst, candidates, fragmentRe, string(m.Bytes()), width) {
				if len(candidates) >= neededKeys {
					if candidate := committedFlag(inst, candidates); candidate != "" {
						return candidate
					}
				}
			}
		}
	}
	if candidate := committedFlag(inst, candidates); candidate != "" {
		return candidate
	}
	width = (inst.ShareBits + 3) / 4
	return "CICADA{" + strings.Repeat("0", inst.ChunkCount*width) + "}"
}
GO
go run /app/cmd/recover.go /app/challenge /app/recovered_flag.txt
test -s /app/recovered_flag.txt
