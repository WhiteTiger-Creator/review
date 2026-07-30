package cli

import "flag"

type AnalyzeOptions struct {
	EventsDir  string
	ConfigDir  string
	PolicyDir  string
	StatePath  string
	OutputDir  string
}

func ParseAnalyzeArgs(args []string) (*AnalyzeOptions, error) {
	fs := flag.NewFlagSet("token-exposure-analyze", flag.ContinueOnError)
	opts := &AnalyzeOptions{}
	fs.StringVar(&opts.EventsDir, "events", "/app/data/events", "events directory")
	fs.StringVar(&opts.ConfigDir, "config", "/app/config", "config directory")
	fs.StringVar(&opts.PolicyDir, "regolib", "/app/opalib", "rego library directory")
	fs.StringVar(&opts.StatePath, "state", "/app/data/state/analysis-state.json", "state file")
	fs.StringVar(&opts.OutputDir, "output", "/output", "output directory")
	if err := fs.Parse(args); err != nil {
		return nil, err
	}
	return opts, nil
}
