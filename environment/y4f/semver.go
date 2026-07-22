package y4f

import "strings"

func cmpVer(a, b string) int {
	pa := strings.Split(StripPreToken(a), ".")
	pb := strings.Split(StripPreToken(b), ".")
	for len(pa) < 3 {
		pa = append(pa, "0")
	}
	for len(pb) < 3 {
		pb = append(pb, "0")
	}
	for i := 0; i < 3; i++ {
		va := atoi(pa[i])
		vb := atoi(pb[i])
		if va != vb {
			return va - vb
		}
	}
	sa := preSuffix(a)
	sb := preSuffix(b)
	if sa != sb {
		if sa == "" {
			return 1
		}
		if sb == "" {
			return -1
		}
		if sa < sb {
			return -1
		}
		return 1
	}
	return 0
}

func StripPreToken(v string) string {
	if idx := strings.Index(v, "-pre."); idx > 0 {
		return v[:idx]
	}
	return v
}

func preSuffix(v string) string {
	if idx := strings.Index(v, "-pre."); idx > 0 {
		return v[idx+1:]
	}
	return ""
}

func atoi(s string) int {
	n := 0
	for _, ch := range s {
		if ch < '0' || ch > '9' {
			break
		}
		n = n*10 + int(ch-'0')
	}
	return n
}
