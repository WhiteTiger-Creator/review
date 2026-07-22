package acquire

import "fmt"

func PulseURL(origin string, chain, pulse uint64) string {
	return fmt.Sprintf("%s/beacon/2.0/chain/%d/pulse/%d", origin, chain, pulse)
}

func CertificateURL(origin, identifier string) string {
	return fmt.Sprintf("%s/beacon/2.0/certificate/%s", origin, identifier)
}
