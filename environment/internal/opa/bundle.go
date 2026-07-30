package opa

import "os/exec"

func Check(policyDir string) error {
	cmd := exec.Command("opa", "check", policyDir)
	return cmd.Run()
}
