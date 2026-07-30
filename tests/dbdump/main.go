// Command dbdump prints the full contents of a bbolt database as JSON:
// {"bucket": {"key": "value", ...}, ...}. It is a verifier-only helper
// compiled at test time from tests-owned source.
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"time"

	bolt "go.etcd.io/bbolt"
)

func main() {
	if len(os.Args) != 2 {
		fmt.Fprintln(os.Stderr, "usage: dbdump <path-to-bbolt-db>")
		os.Exit(2)
	}
	db, err := bolt.Open(os.Args[1], 0o600, &bolt.Options{
		ReadOnly: true,
		Timeout:  3 * time.Second,
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, "open:", err)
		os.Exit(1)
	}
	defer db.Close()

	out := map[string]map[string]string{}
	err = db.View(func(tx *bolt.Tx) error {
		return tx.ForEach(func(name []byte, b *bolt.Bucket) error {
			m := map[string]string{}
			if err := b.ForEach(func(k, v []byte) error {
				m[string(k)] = string(v)
				return nil
			}); err != nil {
				return err
			}
			out[string(name)] = m
			return nil
		})
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, "read:", err)
		os.Exit(1)
	}
	if err := json.NewEncoder(os.Stdout).Encode(out); err != nil {
		fmt.Fprintln(os.Stderr, "encode:", err)
		os.Exit(1)
	}
}
