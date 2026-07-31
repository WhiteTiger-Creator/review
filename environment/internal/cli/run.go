package cli

import (
	"racklight/drainwave/internal/contract"
	"racklight/drainwave/internal/input"
	"racklight/drainwave/internal/model"
	"racklight/drainwave/internal/output"
	"racklight/drainwave/internal/planner"
)

func Run(arguments []string) int {
	if len(arguments) != 3 {
		return invalid()
	}
	inventory, policy, err, ioError := input.Load(arguments[0], arguments[1])
	if err != nil {
		if ioError {
			return ioFailure()
		}
		return invalid()
	}
	waves, possible := planner.Plan(inventory, policy)
	report := model.Report{Status: contract.StatusUnsatisfiable, Reason: contract.NoScheduleReason}
	exitCode := contract.ExitUnsatisfiable
	if possible {
		report = planner.Report(inventory, policy, waves)
		exitCode = contract.ExitOK
	}
	data, err := output.Encode(report)
	if err != nil {
		return ioFailure()
	}
	if err := output.WriteAtomic(arguments[2], data); err != nil {
		return ioFailure()
	}
	return exitCode
}
