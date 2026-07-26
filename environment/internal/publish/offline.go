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
			s.SignedPublish = v == "true"
		}
	}
	return s, sc.Err()
}

type Issue struct {
	Kind     string
	EntityID string
	Detail   string
}

func Check(s Settings, requireOffline, failOnProject bool) []Issue {
	out := []Issue{}
	if failOnProject && s.RepositoriesMode == "FAIL_ON_PROJECT_REPOS" {
		out = append(out, Issue{Kind: "PROJECT_REPO_FORBIDDEN", EntityID: "repositories_mode", Detail: s.RepositoriesMode})
	}
	if requireOffline {
		if s.VaultPath != "/app/meshgrid/offline-vault" {
			out = append(out, Issue{Kind: "OFFLINE_REPO_MISCONFIG", EntityID: "vault_path", Detail: s.VaultPath})
		}
		if !s.SignedPublish {
			out = append(out, Issue{Kind: "PUBLISH_UNSIGNED", EntityID: "signed_publish", Detail: ""})
		}
	}
	return out
}
