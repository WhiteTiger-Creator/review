package main

import (
	"fmt"
	"os"

	"cabrelay/n3seq"
)

func usage() {
	fmt.Fprintf(os.Stderr, "usage: cabrelay <apply|resume|status> [--config PATH] [--root PATH]\n")
}

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	cmd := os.Args[1]
	config := "/app/environment/configs/transfer.toml"
	root := "/app/var"
	args := os.Args[2:]
	for i := 0; i < len(args); i++ {
		switch args[i] {
		case "--config":
			i++
			if i < len(args) {
				config = args[i]
			}
		case "--root":
			i++
			if i < len(args) {
				root = args[i]
			}
		}
	}
	var err error
	switch cmd {
	case "apply":
		err = n3seq.Apply(config, root)
	case "resume":
		err = n3seq.Resume(config, root)
	case "status":
		err = n3seq.StatusCmd(root)
	default:
		usage()
		os.Exit(2)
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "cabrelay: %v\n", err)
		os.Exit(1)
	}
}
