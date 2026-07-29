package slot

var labelCache = map[string]string{}

func CacheLabel(id, label string) {
	labelCache[id] = label
}

func LabelFor(id string) string {
	return labelCache[id]
}
