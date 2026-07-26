package semver

import "sort"

// Compare orders two versions: -1 if a sorts before b, 0 when equal, 1 after.
// A release sorts after every prerelease that shares its core fields.
func Compare(a, b Version) int {
	if c := cmpInt(a.Major, b.Major); c != 0 {
		return c
	}
	if c := cmpInt(a.Minor, b.Minor); c != 0 {
		return c
	}
	if c := cmpInt(a.Patch, b.Patch); c != 0 {
		return c
	}
	switch {
	case a.RC == b.RC:
		return 0
	case a.RC == 0:
		return 1
	case b.RC == 0:
		return -1
	}
	return cmpInt(a.RC, b.RC)
}

// Less reports whether a sorts before b.
func Less(a, b Version) bool { return Compare(a, b) < 0 }

// SortDesc orders versions newest first, in place.
func SortDesc(vs []Version) {
	sort.Slice(vs, func(i, j int) bool { return Compare(vs[i], vs[j]) > 0 })
}

func cmpInt(a, b int) int {
	switch {
	case a < b:
		return -1
	case a > b:
		return 1
	}
	return 0
}
