package p3

import (
	"sort"

	"bnmod/internal"
)

// CitePin returns the first write-capable tag in row packing order.
func CitePin(rows []internal.RowTag) string {
	for _, r := range rows {
		if r.Role == 0 && r.Tag != "" {
			return r.Tag
		}
	}
	return ""
}

// CiteLex returns the lexicographically first write-capable tag.
func CiteLex(rows []internal.RowTag) string {
	wtags := make([]string, 0, len(rows))
	for _, r := range rows {
		if r.Role == 0 && r.Tag != "" {
			wtags = append(wtags, r.Tag)
		}
	}
	if len(wtags) == 0 {
		return ""
	}
	sort.Strings(wtags)
	return wtags[0]
}
