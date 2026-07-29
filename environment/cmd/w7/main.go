package main

import (
	"flag"
	"fmt"
	"os"

	"k7w"
)

func main() {
	if len(os.Args) > 1 {
		switch os.Args[1] {
		case "check-bundle":
			if err := k7w.CheckBundle("/app/environment"); err != nil {
				fmt.Fprintf(os.Stderr, "check: %v\n", err)
				os.Exit(2)
			}
			fmt.Println("ok")
			return
		case "emit":
			fs := flag.NewFlagSet("emit", flag.ExitOnError)
			out := fs.String("out", "/app/output/k7_witness_report.json", "output path")
			_ = fs.Parse(os.Args[2:])
			if err := k7w.RunEmit("/app/environment", *out); err != nil {
				fmt.Fprintf(os.Stderr, "emit: %v\n", err)
				os.Exit(2)
			}
			return
		}
	}
	fmt.Println("w7 emit --out /app/output/k7_witness_report.json")
	fmt.Println("w7 check-bundle")
	fmt.Println("Build with: make -C /app/environment build")
}
