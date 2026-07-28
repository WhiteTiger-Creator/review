package main

import (
	"gobnd/k2"
	"gobnd/p7"
)

func stageA(repo, release string) ([]string, string, error) {
	commits, err := p7.FnR8(repo, release)
	if err != nil {
		return nil, "", err
	}
	return k2.FnS2(repo, commits)
}
