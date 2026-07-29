package main

import (
	"encoding/binary"
	"encoding/hex"
	"flag"
	"fmt"
	"os"

	"k7w/internal/wire"
)

func main() {
	flag.Parse()
	if len(flag.Args()) < 2 || flag.Arg(0) != "observe" {
		fmt.Println("dy observe --chunk <file>")
		os.Exit(2)
	}
	path := ""
	for i := 1; i < len(flag.Args()); i++ {
		if flag.Arg(i) == "--chunk" && i+1 < len(flag.Args()) {
			path = flag.Arg(i + 1)
		}
	}
	if path == "" {
		os.Exit(2)
	}
	frame, err := os.ReadFile(path)
	if err != nil {
		os.Exit(2)
	}
	stamp, err := wire.CanonStamp(frame)
	if err != nil {
		os.Exit(2)
	}
	body, _ := wire.BodyOf(frame)
	fmt.Printf(`{"canon_hex":"%s","body_len":%d}`+"\n", stamp, len(body))
}
