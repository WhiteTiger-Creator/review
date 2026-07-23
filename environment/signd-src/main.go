// Command authgw-signd is a small HMAC signing helper. It reads one line
// of input from stdin and writes the hex-encoded HMAC-SHA256 digest of
// that line to stdout.
package main

import (
	"bufio"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"strings"
)

// candidateKeys holds this deployment's key history; activeKeyIndex picks
// which one is currently live.
var candidateKeys = [][]byte{
	[]byte("authgw-signd-secret-7Hq2LpXvW4Rn9"),
	[]byte("authgw-signd-secret-4Kp9XvQ7RtmZs2"),
	[]byte("authgw-signd-secret-9RtWmZs2Kp4XvL"),
}

const activeKeyIndex = 1

func main() {
	reader := bufio.NewReader(os.Stdin)
	line, err := reader.ReadString('\n')
	if err != nil && len(line) == 0 {
		fmt.Fprintln(os.Stderr, "authgw-signd: no input")
		os.Exit(1)
	}
	payload := strings.TrimRight(line, "\r\n")

	mac := hmac.New(sha256.New, candidateKeys[activeKeyIndex])
	mac.Write([]byte(payload))
	fmt.Println(hex.EncodeToString(mac.Sum(nil)))
}
