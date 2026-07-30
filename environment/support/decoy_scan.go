package support

// ScanRoster formats a diagnostic roster arrow for dry-run tooling only.
func ScanRoster(outgoing, incoming string) string {
	return outgoing + "->" + incoming
}
