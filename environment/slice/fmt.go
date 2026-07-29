package slice

import (
	"fmt"
	"k7w/internal/model"
)

func FormatChunk(c model.Chunk) string {
	return fmt.Sprintf("%02x:%x", c.Tag, c.Value)
}
