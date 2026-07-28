package p12

import "bnmod/internal"

// AfterScore is an optional post-score adapter installed by the evaluation driver.
var AfterScore func(led *internal.Ledger, rows []internal.RowTag, armIx int) []internal.RowTag

// AfterFold is an optional post-fold adapter installed by the evaluation driver.
var AfterFold func(unit internal.LatticeUnit, rows []internal.RowTag) internal.LatticeUnit
