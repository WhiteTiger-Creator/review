package verify

import (
	"fmt"
	"time"

	"beaconaudit/internal/codec"
	"beaconaudit/internal/cryptoutil"
	"beaconaudit/internal/model"
)

func CheckContinuity(pulses []EvidencePulse, policy model.Policy) (model.ContinuityResults, error) {
	result := model.ContinuityResults{IndexesConsecutive: true, TimestampsConsecutive: true, PreviousLinksVerified: true, PrecommitmentsVerified: true}
	for index := 1; index < len(pulses); index++ {
		previous, current := pulses[index-1].Pulse, pulses[index].Pulse
		if current.PulseIndex != previous.PulseIndex+1 {
			return result, fmt.Errorf("pulse indexes are not consecutive")
		}
		previousTime, _ := time.Parse("2006-01-02T15:04:05.000Z", previous.TimeStamp)
		currentTime, _ := time.Parse("2006-01-02T15:04:05.000Z", current.TimeStamp)
		if currentTime.Sub(previousTime) != time.Duration(policy.PeriodMS)*time.Millisecond {
			return result, fmt.Errorf("pulse timestamps are not consecutive")
		}
		link, ok := current.Link("previous")
		if !ok || link != previous.OutputValue {
			return result, fmt.Errorf("pulse %d previous link mismatch", current.PulseIndex)
		}
		local, err := codec.Hex(current.LocalRandomValue, 64, "localRandomValue")
		if err != nil {
			return result, err
		}
		if cryptoutil.SHA512(local) != previous.PrecommitmentValue {
			return result, fmt.Errorf("pulse %d precommitment does not open", previous.PulseIndex)
		}
	}
	return result, nil
}
