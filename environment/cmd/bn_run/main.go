package main

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"bnmod/internal"
	_ "bnmod/ocneval"
	_ "bnmod/ocnfix"
	"bnmod/pipe/p12"
	"bnmod/pipe/p34"
)

func main() {
	root := "/app/environment"
	out := "/app/output/invariant_proof_log.json"
	for i := 1; i < len(os.Args); i++ {
		a := os.Args[i]
		switch {
		case a == "-root" && i+1 < len(os.Args):
			i++
			root = os.Args[i]
		case a == "-out" && i+1 < len(os.Args):
			i++
			out = os.Args[i]
		}
	}
	if err := os.MkdirAll(filepath.Dir(out), 0o755); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	internal.WriteWarm(root)

	led := internal.NewLedger(root, out)
	led.Reset()

	arms, err := loadArms(filepath.Join(root, "data", "xtra_clk.toml"))
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	for i, arm := range arms {
		if arm.Kind != "hold" {
			continue
		}
		bundle := p12.Run(led, root, arm.Seed, i)
		bundle.Unit.Arm = arm.Name
		_ = p34.Run(led, bundle.Unit, arms, i, out)
	}
}

func loadArms(path string) ([]internal.JumpArm, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var arms []internal.JumpArm
	var cur *internal.JumpArm
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if line == "[[arm]]" {
			if cur != nil {
				arms = append(arms, *cur)
			}
			cur = &internal.JumpArm{}
			continue
		}
		if cur == nil {
			continue
		}
		switch {
		case strings.HasPrefix(line, "name"):
			cur.Name = unquote(afterEq(line))
		case strings.HasPrefix(line, "kind"):
			cur.Kind = unquote(afterEq(line))
		case strings.HasPrefix(line, "seed"):
			v, _ := strconv.ParseUint(afterEq(line), 10, 64)
			cur.Seed = v
		case strings.HasPrefix(line, "jump"):
			v, _ := strconv.Atoi(afterEq(line))
			cur.Jump = v
		case strings.HasPrefix(line, "rotate"):
			v, _ := strconv.Atoi(afterEq(line))
			cur.Rotate = v
		}
	}
	if cur != nil {
		arms = append(arms, *cur)
	}
	return arms, sc.Err()
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
