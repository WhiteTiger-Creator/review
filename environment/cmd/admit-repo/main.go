package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"gobnd/lib/m3"
)

func main() {
	repo := flag.String("repo", "", "path to git repository")
	release := flag.String("release-ref", "", "release ref to admit")
	policy := flag.String("policy", "/app/environment/policy/signer_matrix.toml", "signer matrix policy")
	rules := flag.String("rules", "/app/environment/policy/release_rules.toml", "release rules")
	out := flag.String("report", "/app/output/object_trust_report.json", "output report path")
	keyHome := flag.String("key-home", "/app/environment/fixtures/keys/gnupg", "GNUPGHOME for signature verification")
	flag.Parse()
	if *repo == "" || *release == "" {
		fmt.Fprintln(os.Stderr, "usage: admit-repo --repo <path> --release-ref <ref> [--policy ...] [--report ...]")
		os.Exit(1)
	}
	absRepo, err := filepath.Abs(*repo)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	code, err := run(absRepo, *release, *policy, *rules, *out, *keyHome)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	os.Exit(code)
}

func run(repo, release, policyPath, rulesPath, outPath, keyHome string) (int, error) {
	m3.ExportGitConfig(repo, keyHome)
	_, _ = m3.LoadReleaseRules(rulesPath)
	commits, code, err := stageA(repo, release)
	records := recordsFor(commits)
	if err != nil {
		rep := m3.Report{
			SchemaVersion: 1,
			RepoPath:      repo,
			ReleaseRef:    release,
			Admitted:      false,
			WalkRecords:   records,
		}
		rep.Rejection = &m3.Rejection{Code: code, Detail: err.Error()}
		_ = m3.WriteReport(outPath, rep)
		return 2, nil
	}
	rep := m3.Report{
		SchemaVersion: 1,
		RepoPath:      repo,
		ReleaseRef:    release,
		WalkRecords:   records,
	}
	ok, vcode, err := stageB(repo, release, policyPath, commits)
	if err != nil || !ok {
		rep.Admitted = false
		if vcode == "" {
			vcode = "TAG_ANCHOR"
		}
		rep.Rejection = &m3.Rejection{Code: vcode, Detail: fmt.Sprintf("coverage failed for %d commits", len(commits))}
		_ = m3.WriteReport(outPath, rep)
		return 2, nil
	}
	rep.Admitted = true
	if err := m3.WriteReport(outPath, rep); err != nil {
		return 1, err
	}
	return 0, nil
}

func recordsFor(commits []string) []m3.WalkRecord {
	records := make([]m3.WalkRecord, 0, len(commits))
	for i, id := range commits {
		records = append(records, m3.WalkRecord{Ordinal: i, Kind: "commit", ObjectID: id})
	}
	return records
}
