// Package semver implements the Slate version grammar: three decimal fields
// with an optional -rc.N prerelease marker.
package semver

import (
	"fmt"
	"strconv"
	"strings"
)

// Version is a parsed Slate version. RC is 0 for a plain release and N for
// the prerelease -rc.N.
type Version struct {
	Major int
	Minor int
	Patch int
	RC    int
}

// Parse reads MAJOR.MINOR.PATCH with an optional -rc.N suffix.
func Parse(s string) (Version, error) {
	var v Version
	core := s
	if i := strings.IndexByte(s, '-'); i >= 0 {
		core = s[:i]
		tail := s[i+1:]
		if !strings.HasPrefix(tail, "rc.") {
			return v, fmt.Errorf("version %q: only -rc.N prereleases exist", s)
		}
		n, err := strconv.Atoi(tail[3:])
		if err != nil || n < 1 {
			return v, fmt.Errorf("version %q: prerelease number must be >= 1", s)
		}
		v.RC = n
	}
	fields := strings.Split(core, ".")
	if len(fields) != 3 {
		return v, fmt.Errorf("version %q: want MAJOR.MINOR.PATCH", s)
	}
	out := make([]int, 3)
	for i, f := range fields {
		if f == "" {
			return v, fmt.Errorf("version %q: empty field", s)
		}
		n, err := strconv.Atoi(f)
		if err != nil || n < 0 {
			return v, fmt.Errorf("version %q: field %d is not a number", s, i+1)
		}
		out[i] = n
	}
	v.Major, v.Minor, v.Patch = out[0], out[1], out[2]
	return v, nil
}

// MustParse is Parse for values already known to be well formed.
func MustParse(s string) Version {
	v, err := Parse(s)
	if err != nil {
		panic(err)
	}
	return v
}

// IsPrerelease reports whether v carries an -rc.N marker.
func (v Version) IsPrerelease() bool { return v.RC > 0 }

// Core drops the prerelease marker.
func (v Version) Core() Version { return Version{Major: v.Major, Minor: v.Minor, Patch: v.Patch} }

func (v Version) String() string {
	s := fmt.Sprintf("%d.%d.%d", v.Major, v.Minor, v.Patch)
	if v.RC > 0 {
		s += fmt.Sprintf("-rc.%d", v.RC)
	}
	return s
}
