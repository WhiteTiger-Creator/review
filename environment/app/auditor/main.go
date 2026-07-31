package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
)

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, "thermal evidence finalizer failed:", err)
		os.Exit(1)
	}
}

func run(args []string) error {
	values := map[string]string{}
	for index := 0; index < len(args); index += 2 {
		if index+1 >= len(args) {
			return errors.New("missing argument value")
		}
		values[args[index]] = args[index+1]
	}
	report := values["--report"]
	output := values["--output"]
	if report == "" || output == "" || values["--db"] == "" {
		return errors.New("--db, --report, and --output are required")
	}
	data, err := os.ReadFile(report)
	if err != nil {
		return err
	}
	var document map[string]json.RawMessage
	if err := json.Unmarshal(data, &document); err != nil {
		return err
	}
	delete(document, "_audit")
	encoded, err := json.Marshal(document)
	if err != nil {
		return err
	}
	encoded = append(encoded, '\n')
	if err := os.MkdirAll(filepath.Dir(output), 0o755); err != nil {
		return err
	}
	return os.WriteFile(output, encoded, 0o644)
}
