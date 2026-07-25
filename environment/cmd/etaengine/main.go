
package main

import (
    "os"

    "github.com/local/etaengine/cli"
)

func main() {
    os.Exit(cli.Run(os.Args[1:]))
}
