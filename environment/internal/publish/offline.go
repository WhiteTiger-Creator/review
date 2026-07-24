package publish

import (
	"bufio"
	"os"
	"strings"
)

type Settings struct {
	RepositoriesMode string
	VaultPath        string
	SignedPublish    bool
}

func Load(path string) (Settings, error) {
	f, err := os.Open(path)
	if err != nil {
		return Settings{}, err
	}
	defer f.Close()
	s := Settings{}
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		idx := strings.Index(line, "=")
		if idx < 0 {
			continue
		}
		k := strings.TrimSpace(line[:idx])
		v := strings.Trim(strings.TrimSpace(line[idx+1:]), `"`)
		switch k {
		case "repositories_mode":
			s.RepositoriesMode = v
		case "vault_path":
			s.VaultPath = v
		case "signed_publish":
			// BUG: invert boolean
			s.SignedPublish = v != "true"
		}
	}
	return s, sc.Err()
}

func Check(s Settings, requireOffline, failOnProject bool) [][2]string {
	findings := [][2]string{}
	if failOnProject {
		// BUG: accepts PREFER_PROJECT
		if s.RepositoriesMode == "FAIL_ON_PROJECT_REPOS" {
			findings = append(findings, [2]string{"PROJECT_REPO_FORBIDDEN", s.RepositoriesMode})
		}
	}
	if requireOffline {
		// BUG: wrong expected path
		if s.VaultPath != "/var/meshgrid/offline-vault" {
			findings = append(findings, [2]string{"OFFLINE_REPO_MISCONFIG", s.VaultPath})
		}
		if !s.SignedPublish {
			findings = append(findings, [2]string{"PUBLISH_UNSIGNED", ""})
		}
	}
	return findings
}
