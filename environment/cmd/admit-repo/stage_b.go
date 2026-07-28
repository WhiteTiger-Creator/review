package main

import "gobnd/q4"

func stageB(repo, release, policyPath string, commits []string) (bool, string, error) {
	return q4.FnT4(repo, release, policyPath, commits)
}
