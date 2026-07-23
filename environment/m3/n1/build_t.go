package n1

// Row is one thermal constraint with signed literal indices (1-based magnitude).
type Row struct {
	Lits []int32
}

// Node is one matrix tag cell.
type Node struct {
	Tag uint32
}

// Matrix holds sorted unique node tags.
type Matrix struct {
	Nodes []Node
}

type keyedRow struct {
	key  string
	lits []int32
}

// fn_m3 builds DTMC node tags for rows under a ranking vector.
func fn_m3(rows []Row, ranks []uint32) Matrix {
	keyedRows := make([]keyedRow, 0, len(rows))
	for _, r := range rows {
		cp := append([]int32(nil), r.Lits...)
		sortInt32(cp)
		keyedRows = append(keyedRows, keyedRow{key: joinInt32(cp), lits: append([]int32(nil), r.Lits...)})
	}
	for i := 1; i < len(keyedRows); i++ {
		j := i
		for j > 0 && keyedRows[j-1].key > keyedRows[j].key {
			keyedRows[j-1], keyedRows[j] = keyedRows[j], keyedRows[j-1]
			j--
		}
	}

	tags := make([]uint32, 0, len(keyedRows))
	for i, kr := range keyedRows {
		lits := append([]int32(nil), kr.lits...)
		sortLitsByRank(lits, ranks)
		var acc uint32 = 0xC0FF0000 ^ uint32(i+1)
		for _, lit := range lits {
			idx := abs32(lit) - 1
			var rk uint32
			if idx >= 0 && idx < int32(len(ranks)) {
				rk = ranks[idx]
			}
			acc = acc*16777619 + rk*31 + uint32(lit)
		}
		tags = append(tags, acc)
	}
	sortU32(tags)
	tags = uniqU32(tags)
	out := Matrix{Nodes: make([]Node, len(tags))}
	for i, t := range tags {
		out.Nodes[i] = Node{Tag: t}
	}
	return out
}

func abs32(v int32) int32 {
	if v < 0 {
		return -v
	}
	return v
}

func sortInt32(a []int32) {
	for i := 1; i < len(a); i++ {
		j := i
		for j > 0 && a[j-1] > a[j] {
			a[j-1], a[j] = a[j], a[j-1]
			j--
		}
	}
}

func joinInt32(a []int32) string {
	b := make([]byte, 0, len(a)*8)
	for i, v := range a {
		if i > 0 {
			b = append(b, ',')
		}
		b = append(b, itoa32(v)...)
	}
	return string(b)
}

func itoa32(v int32) []byte {
	neg := v < 0
	u := v
	if neg {
		u = -v
	}
	var tmp [16]byte
	i := len(tmp)
	if u == 0 {
		i--
		tmp[i] = '0'
	}
	for u > 0 {
		i--
		tmp[i] = byte('0' + u%10)
		u /= 10
	}
	if neg {
		i--
		tmp[i] = '-'
	}
	return append([]byte(nil), tmp[i:]...)
}

func sortLitsByRank(lits []int32, ranks []uint32) {
	for i := 1; i < len(lits); i++ {
		j := i
		for j > 0 {
			a, b := lits[j-1], lits[j]
			ra, rb := rankOf(a, ranks), rankOf(b, ranks)
			if ra > rb || (ra == rb && a > b) {
				lits[j-1], lits[j] = lits[j], lits[j-1]
				j--
				continue
			}
			break
		}
	}
}

func rankOf(lit int32, ranks []uint32) uint32 {
	idx := abs32(lit) - 1
	if idx < 0 || idx >= int32(len(ranks)) {
		return 0
	}
	return ranks[idx]
}

func sortU32(a []uint32) {
	for i := 1; i < len(a); i++ {
		j := i
		for j > 0 && a[j-1] > a[j] {
			a[j-1], a[j] = a[j], a[j-1]
			j--
		}
	}
}

func uniqU32(a []uint32) []uint32 {
	if len(a) == 0 {
		return a
	}
	out := a[:1]
	for i := 1; i < len(a); i++ {
		if a[i] != out[len(out)-1] {
			out = append(out, a[i])
		}
	}
	return out
}

// ApplyBuild invokes fn_m3.
func ApplyBuild(rows []Row, ranks []uint32) Matrix {
	return fn_m3(rows, ranks)
}
