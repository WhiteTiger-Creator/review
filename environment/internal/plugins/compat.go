package plugins

import (
	"bufio"
	"os"
	"strconv"
	"strings"
)

type Request struct {
	ID        string
	Version   string
	MinMajor  int
	MinMinor  int
	HasMin    bool
}

var defaults = map[string][2]int{
	"com.meshgrid.wireloom":         {8, 7},
	"com.meshgrid.depknit":          {8, 8},
	"com.meshgrid.artifactseal":     {8, 10},
	"com.meshgrid.pluginbridge":     {8, 5},
	"com.meshgrid.releasemesh":      {8, 9},
	"com.meshgrid.cataloghub":       {8, 10},
	"org.gradle.publish-offline":    {8, 6},
}

func LoadRequests(path string) ([]Request, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var reqs []Request
	var cur *Request
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if line == "[[plugins]]" {
			if cur != nil {
				reqs = append(reqs, *cur)
			}
			cur = &Request{}
			continue
		}
		if cur == nil {
			continue
		}
		k, v, ok := splitKV(line)
		if !ok {
			continue
		}
		v = strings.Trim(v, `"`)
		switch k {
		case "id":
			cur.ID = v
		case "version":
			cur.Version = v
		case "min_gradle":
			maj, min, ok := parseMajMin(v)
			if ok {
				cur.MinMajor = maj
				cur.MinMinor = min
				cur.HasMin = true
			}
		}
	}
	if cur != nil {
		reqs = append(reqs, *cur)
	}
	return reqs, sc.Err()
}

func splitKV(line string) (string, string, bool) {
	idx := strings.Index(line, "=")
	if idx < 0 {
		return "", "", false
	}
	return strings.TrimSpace(line[:idx]), strings.TrimSpace(line[idx+1:]), true
}

func parseMajMin(s string) (int, int, bool) {
	parts := strings.Split(s, ".")
	if len(parts) != 2 {
		return 0, 0, false
	}
	a, err1 := strconv.Atoi(parts[0])
	b, err2 := strconv.Atoi(parts[1])
	if err1 != nil || err2 != nil {
		return 0, 0, false
	}
	return a, b, true
}

// Incompatible intentionally wrong: uses string compare on "major.minor".
func Incompatible(req Request, gradleMajor, gradleMinor int) bool {
	minMaj, minMin := 0, 0
	if req.HasMin {
		minMaj, minMin = req.MinMajor, req.MinMinor
	} else if d, ok := defaults[req.ID]; ok {
		minMaj, minMin = d[0], d[1]
	} else {
		return false
	}
	// BUG: lexicographic compare of formatted strings
	have := format(gradleMajor, gradleMinor)
	need := format(minMaj, minMin)
	return have < need
}

func format(maj, min int) string {
	return strconv.Itoa(maj) + "." + strconv.Itoa(min)
}
