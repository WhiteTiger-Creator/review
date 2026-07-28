package m3

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"strings"
)

func ExportGitConfig(repo, keyHome string) {
	if keyHome != "" {
		_ = os.Setenv("GNUPGHOME", keyHome)
	}
	_, _ = GitExec(repo, "config", "--local", "user.signingkey", "")
	_ = exec.Command("git", "config", "--global", "--add", "safe.directory", repo).Run()
}

func GitExec(repo string, args ...string) (string, error) {
	cmd := exec.Command("git", args...)
	cmd.Dir = repo
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("git %s: %v: %s", strings.Join(args, " "), err, strings.TrimSpace(stderr.String()))
	}
	return strings.TrimSpace(stdout.String()), nil
}
