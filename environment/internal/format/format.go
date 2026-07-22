package format

func LooksLikeFlag(value string) bool {
	if len(value) < 18 || value[:7] != "CICADA{" || value[len(value)-1] != '}' {
		return false
	}
	body := value[7 : len(value)-1]
	if len(body)%10 != 0 {
		return false
	}
	for _, ch := range body {
		if !((ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f')) {
			return false
		}
	}
	return true
}
