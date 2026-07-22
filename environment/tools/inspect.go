package main

import (
	"cicada/recovery/internal/challenge"
	"fmt"
	"os"
)

func main() {
	dir := "/app/challenge"
	if len(os.Args) > 1 {
		dir = os.Args[1]
	}
	inst, err := challenge.Load(dir)
	if err != nil {
		panic(err)
	}
	fmt.Println(inst.N.Text(16))
}
