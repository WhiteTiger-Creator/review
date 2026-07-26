package cartographer

// Shortest route counts are canonical unsigned decimal strings without leading zeros.
// Implementations must support values larger than sixty-four bits.
func countingDoc() string {
	return "arbitrary-precision decimal count"
}
