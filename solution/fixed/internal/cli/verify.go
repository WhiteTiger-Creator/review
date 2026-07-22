package cli

import (
	"fmt"

	"beaconaudit/internal/config"
	"beaconaudit/internal/model"
	"beaconaudit/internal/receipt"
	"beaconaudit/internal/verify"
)

func runVerify(arguments []string) error {
	flags, err := parse("verify", arguments, true)
	if err != nil {
		return err
	}
	item, err := loadCase(flags.casePath)
	if err != nil {
		return err
	}
	var policy model.Policy
	if err := config.Load(item.PolicyPath, &policy); err != nil {
		return err
	}
	if err := config.ValidatePolicy(policy); err != nil {
		return err
	}
	var trust model.Trust
	if err := config.Load(item.TrustPath, &trust); err != nil {
		return err
	}
	if err := config.ValidateTrust(trust); err != nil {
		return err
	}
	if err := receipt.ValidateDestination(flags.receipt, flags.directory); err != nil {
		return err
	}
	result, err := verify.Audit(item, policy, trust, flags.directory)
	if err != nil {
		return err
	}
	if err := receipt.Write(flags.receipt, result); err != nil {
		return err
	}
	fmt.Printf("verified %d signed pulses; receipt %s\n", len(result.Pulses), flags.receipt)
	return nil
}
