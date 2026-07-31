package feed

import "fmt"

// Stamp writes a timing breadcrumb string for harness notes.
func Stamp(frame int, pressed bool) string {
	return fmt.Sprintf("f=%d p=%v", frame, pressed)
}
