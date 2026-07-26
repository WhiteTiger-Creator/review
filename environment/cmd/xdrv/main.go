package main

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"adreq/nx"
	"adreq/pipe/p12"
	"adreq/pipe/p34"
)

func main() {
	root := "/app/environment"
	out := "/app/output/invariant.yaml"
	arm := 1 // default held-out meta arm
	for i := 1; i < len(os.Args); i++ {
		a := os.Args[i]
		switch {
		case a == "-root" && i+1 < len(os.Args):
			i++
			root = os.Args[i]
		case a == "-out" && i+1 < len(os.Args):
			i++
			out = os.Args[i]
		case a == "-arm" && i+1 < len(os.Args):
			i++
			v, _ := strconv.Atoi(os.Args[i])
			arm = v
		}
	}
	if err := os.MkdirAll(filepath.Dir(out), 0o755); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	lanes, err := loadLanes(filepath.Join(root, "data", "xtra_lanes.toml"))
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	bundle, err := p12.Run(root, arm)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := p34.Run(bundle, lanes, arm, out); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func loadLanes(path string) ([]nx.Lane, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var lanes []nx.Lane
	var cur *nx.Lane
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if line == "[[lane]]" {
			if cur != nil {
				lanes = append(lanes, *cur)
			}
			cur = &nx.Lane{}
			continue
		}
		if cur == nil {
			continue
		}
		if strings.HasPrefix(line, "name") {
			cur.Name = unquote(afterEq(line))
		} else if strings.HasPrefix(line, "kind") {
			cur.Kind = unquote(afterEq(line))
		} else if strings.HasPrefix(line, "arm") {
			cur.Arm = unquote(afterEq(line))
		} else if strings.HasPrefix(line, "seed") {
			v, _ := strconv.ParseUint(afterEq(line), 10, 32)
			cur.Seed = uint32(v)
		} else if strings.HasPrefix(line, "fuzz_rounds") {
			v, _ := strconv.Atoi(afterEq(line))
			cur.N = v
		}
	}
	if cur != nil {
		lanes = append(lanes, *cur)
	}
	return lanes, sc.Err()
}

func afterEq(s string) string {
	i := strings.IndexByte(s, '=')
	if i < 0 {
		return ""
	}
	return strings.TrimSpace(s[i+1:])
}

func unquote(s string) string {
	s = strings.TrimSpace(s)
	if len(s) >= 2 && s[0] == '"' && s[len(s)-1] == '"' {
		return s[1 : len(s)-1]
	}
	return s
}
