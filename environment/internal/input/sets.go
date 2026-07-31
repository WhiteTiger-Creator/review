package input

const maxContractInteger = 1_000_000

func addUnique(values map[string]bool, value string) bool {
	if value == "" || values[value] {
		return false
	}
	values[value] = true
	return true
}

func boundedNonNegativeMap(values map[string]int) bool {
	if values == nil {
		return false
	}
	for key, value := range values {
		if key == "" || value < 0 || value > maxContractInteger {
			return false
		}
	}
	return true
}
