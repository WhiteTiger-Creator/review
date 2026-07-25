package krel

import (
	"fmt"

	"github.com/local/etaengine/shipkv"
	"github.com/local/etaengine/types"
)

func Stage(root string, settings types.InferSettings) error {
	reg, err := shipkv.LoadRegistry(root)
	if err != nil {
		return err
	}
	st := types.StagedState{
		Generation: reg.ActiveGen + 1,
		Settings:   settings,
		Incomplete: true,
		ParentGen:  reg.ActiveGen,
	}
	return shipkv.SaveStaged(root, st)
}

func Finalize(root string) error {
	staged, ok, err := shipkv.LoadStaged(root)
	if err != nil {
		return err
	}
	if !ok {
		return fmt.Errorf("no staged promotion")
	}
	staged.Incomplete = false
	return shipkv.SaveStaged(root, staged)
}

func ActivateCutover(root string) error {
	reg, err := shipkv.LoadRegistry(root)
	if err != nil {
		return err
	}
	staged, ok, err := shipkv.LoadStaged(root)
	if err != nil {
		return err
	}
	if !ok {
		return fmt.Errorf("no staged promotion")
	}
	reg.ActiveGen = staged.Generation
	reg.Lineage = append(reg.Lineage, staged.Generation)
	reg.EpochToken = fmt.Sprintf("epoch-%d", staged.Generation)
	return shipkv.SaveRegistry(root, reg)
}

func Rollback(root string) error {
	reg, err := shipkv.LoadRegistry(root)
	if err != nil {
		return err
	}
	if reg.ActiveGen == 0 {
		return fmt.Errorf("nothing to rollback")
	}
	_ = shipkv.ClearStaged(root)
	if len(reg.Lineage) > 0 {
		reg.Lineage = reg.Lineage[:len(reg.Lineage)-1]
	}
	reg.ActiveGen = reg.ActiveGen - 1
	reg.EpochToken = fmt.Sprintf("epoch-%d", reg.ActiveGen)
	return shipkv.SaveRegistry(root, reg)
}
