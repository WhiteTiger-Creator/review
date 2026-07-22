package d8l

import "encoding/base64"

func FnArchiveDecode(blob string) ([]byte, error) {
	return base64.StdEncoding.DecodeString(blob)
}
