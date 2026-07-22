package cli

import (
	"flag"
	"fmt"
)

type commonFlags struct {
	casePath  string
	directory string
	receipt   string
}

func parse(name string, arguments []string, needsReceipt bool) (commonFlags, error) {
	set := flag.NewFlagSet(name, flag.ContinueOnError)
	set.SetOutput(discardWriter{})
	var values commonFlags
	set.StringVar(&values.casePath, "case", "", "case JSON path")
	set.StringVar(&values.directory, "directory", "", "evidence directory")
	if needsReceipt {
		set.StringVar(&values.receipt, "receipt", "", "receipt JSON path")
	}
	if err := set.Parse(arguments); err != nil {
		return values, err
	}
	if set.NArg() != 0 || values.casePath == "" || values.directory == "" || (needsReceipt && values.receipt == "") {
		return values, fmt.Errorf("%s requires --case and --directory%s", name, map[bool]string{true: " and --receipt", false: ""}[needsReceipt])
	}
	return values, nil
}

type discardWriter struct{}

func (discardWriter) Write(data []byte) (int, error) { return len(data), nil }
