package cli

import (
	"fmt"

	"beaconaudit/internal/acquire"
)

func runAcquire(arguments []string) error {
	flags, err := parse("acquire", arguments, false)
	if err != nil {
		return err
	}
	item, err := loadCase(flags.casePath)
	if err != nil {
		return err
	}
	if err := acquire.Interval(item, flags.directory); err != nil {
		return err
	}
	fmt.Printf("acquired pulses %d-%d from %s\n", item.FirstPulse, item.LastPulse, item.APIOrigin)
	return nil
}
