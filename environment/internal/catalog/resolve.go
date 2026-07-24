package catalog

import (
	"bufio"
	"os"
	"strings"
)

type Catalog struct {
	Versions  map[string]string
	Libraries map[string]Library
	Bundles   map[string][]string
	Plugins   map[string]PluginAlias
}

type Library struct {
	Module     string
	Version    string
	VersionRef string
	Inline     bool
}

type PluginAlias struct {
	ID         string
	VersionRef string
}

func Load(path string) (*Catalog, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	c := &Catalog{
		Versions:  map[string]string{},
		Libraries: map[string]Library{},
		Bundles:   map[string][]string{},
		Plugins:   map[string]PluginAlias{},
	}
	section := ""
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if strings.HasPrefix(line, "[") && strings.HasSuffix(line, "]") {
			section = strings.Trim(line, "[]")
			continue
		}
		switch section {
		case "versions":
			k, v, ok := splitKV(line)
			if ok {
				c.Versions[k] = strings.Trim(v, `"`)
			}
		case "libraries":
			name, rest, ok := splitKV(line)
			if !ok {
				continue
			}
			lib := parseLibrary(rest)
			c.Libraries[name] = lib
		case "bundles":
			name, rest, ok := splitKV(line)
			if !ok {
				continue
			}
			rest = strings.TrimSpace(rest)
			rest = strings.TrimPrefix(rest, "[")
			rest = strings.TrimSuffix(rest, "]")
			parts := strings.Split(rest, ",")
			out := make([]string, 0, len(parts))
			for _, p := range parts {
				p = strings.TrimSpace(p)
				p = strings.Trim(p, `"`)
				if p != "" {
					out = append(out, p)
				}
			}
			c.Bundles[name] = out
		case "plugins":
			name, rest, ok := splitKV(line)
			if !ok {
				continue
			}
			c.Plugins[name] = parsePluginAlias(rest)
		}
	}
	return c, sc.Err()
}

func splitKV(line string) (string, string, bool) {
	idx := strings.Index(line, "=")
	if idx < 0 {
		return "", "", false
	}
	return strings.TrimSpace(line[:idx]), strings.TrimSpace(line[idx+1:]), true
}

func parseLibrary(rest string) Library {
	lib := Library{}
	rest = strings.TrimSpace(rest)
	rest = strings.TrimPrefix(rest, "{")
	rest = strings.TrimSuffix(rest, "}")
	for _, part := range strings.Split(rest, ",") {
		part = strings.TrimSpace(part)
		k, v, ok := splitKV(part)
		if !ok {
			continue
		}
		v = strings.Trim(v, `"`)
		switch k {
		case "module":
			lib.Module = v
		case "version.ref":
			lib.VersionRef = v
		case "version":
			lib.Version = v
			lib.Inline = true
		}
	}
	return lib
}

func parsePluginAlias(rest string) PluginAlias {
	p := PluginAlias{}
	rest = strings.TrimSpace(rest)
	rest = strings.TrimPrefix(rest, "{")
	rest = strings.TrimSuffix(rest, "}")
	for _, part := range strings.Split(rest, ",") {
		part = strings.TrimSpace(part)
		k, v, ok := splitKV(part)
		if !ok {
			continue
		}
		v = strings.Trim(v, `"`)
		switch k {
		case "id":
			p.ID = v
		case "version.ref":
			p.VersionRef = v
		}
	}
	return p
}

// ResolveLibraryVersion intentionally wrong: prefers inline over ref and ignores versions table mismatch detection helper.
func ResolveLibraryVersion(c *Catalog, lib Library) (string, string, bool) {
	if lib.Inline {
		return lib.Version, "", true
	}
	if lib.VersionRef != "" {
		// BUG: returns ref name as version when missing instead of unresolved
		if v, ok := c.Versions[lib.VersionRef]; ok {
			return v, lib.VersionRef, true
		}
		return lib.VersionRef, lib.VersionRef, true
	}
	return "", "", false
}

func AliasConflicts(c *Catalog) []string {
	out := []string{}
	for alias := range c.Bundles {
		if _, ok := c.Libraries[alias]; ok {
			out = append(out, alias)
		}
	}
	return out
}
