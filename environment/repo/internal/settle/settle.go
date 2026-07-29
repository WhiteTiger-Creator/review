// Package settle scores a finished hand from the log.
package settle

import (
	"errors"

	"scoreboard/handsettle/internal/table"
)

// Settle works out the settlement of one finished hand: its han and fu, the yaku it
// holds and what the winner collects.
func Settle(h table.Hand) (table.Result, error) {
	return table.Result{}, errors.New("hand settlement is not implemented yet")
}
