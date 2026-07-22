package main

import (
	"cicada/recovery/internal/attack"
	"cicada/recovery/internal/challenge"
	"fmt"
	"os"
)

func main() {
	challengeDir := "/app/challenge"
	outputPath := "/app/recovered_flag.txt"
	if len(os.Args) > 1 {
		challengeDir = os.Args[1]
	}
	if len(os.Args) > 2 {
		outputPath = os.Args[2]
	}
	instance, err := challenge.Load(challengeDir)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	flag := attack.Recover(instance)
	if err := os.WriteFile(outputPath, []byte(flag+"\n"), 0644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
