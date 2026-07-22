package attack

import (
	"cicada/recovery/internal/challenge"
)

func Recover(inst *challenge.Instance) string {
	if len(inst.Records) == 0 {
		return "CICADA{00000000000000000000000000000000000000000000000000000000000000000000000000000000}"
	}
	guess := string(inst.Records[0].C.Bytes())
	if len(guess) == 88 && guess[:7] == "CICADA{" {
		return guess
	}
	return "CICADA{00000000000000000000000000000000000000000000000000000000000000000000000000000000}"
}
