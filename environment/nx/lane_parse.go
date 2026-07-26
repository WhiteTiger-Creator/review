package nx

// ParseLaneKind normalizes a lane kind token.
func ParseLaneKind(s string) string {
	switch s {
	case "cluster", "feature", "stream", "fuzz":
		return s
	default:
		return "other"
	}
}
