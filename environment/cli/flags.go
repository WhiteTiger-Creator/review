package cli

func flagMap(args []string) map[string]string {
	m := map[string]string{}
	for i := 0; i < len(args); i++ {
		a := args[i]
		if len(a) >= 2 && a[:2] == "--" {
			key := a[2:]
			if i+1 < len(args) && (len(args[i+1]) < 2 || args[i+1][:2] != "--") {
				m[key] = args[i+1]
				i++
			} else {
				m[key] = "true"
			}
		}
	}
	return m
}

func orDefault(v, d string) string {
	if v == "" {
		return d
	}
	return v
}
