package cli

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/local/etaengine/shipkv"
)

func cmdStatus(args []string) int {
	fm := flagMap(args)
	root := fm["root"]
	if root == "" {
		root = "/app/environment"
	}
	reg, err := shipkv.LoadRegistry(root)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	b, _ := json.MarshalIndent(reg, "", "  ")
	fmt.Println(string(b))
	return 0
}
