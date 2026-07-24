#!/usr/bin/env bash
set -euo pipefail

cd /app

cat > /app/internal/catalog/resolve.go <<'EOF'
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
			c.Libraries[name] = parseLibrary(rest)
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

func ResolveLibraryVersion(c *Catalog, lib Library) (string, string, bool) {
	if lib.VersionRef != "" {
		if v, ok := c.Versions[lib.VersionRef]; ok {
			return v, lib.VersionRef, true
		}
		return "", lib.VersionRef, false
	}
	if lib.Inline {
		return lib.Version, "", true
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
	sortStrings(out)
	return out
}

func UnresolvedRefs(c *Catalog) []string {
	seen := map[string]struct{}{}
	out := []string{}
	for _, lib := range c.Libraries {
		if lib.VersionRef == "" {
			continue
		}
		if _, ok := c.Versions[lib.VersionRef]; ok {
			continue
		}
		if _, ok := seen[lib.VersionRef]; ok {
			continue
		}
		seen[lib.VersionRef] = struct{}{}
		out = append(out, lib.VersionRef)
	}
	sortStrings(out)
	return out
}

func InlineDrifts(c *Catalog) []string {
	out := []string{}
	for alias, lib := range c.Libraries {
		if !lib.Inline {
			continue
		}
		if v, ok := c.Versions[alias]; ok && v != lib.Version {
			out = append(out, alias)
		}
	}
	sortStrings(out)
	return out
}

func sortStrings(in []string) {
	for i := 0; i < len(in); i++ {
		for j := i + 1; j < len(in); j++ {
			if in[j] < in[i] {
				in[i], in[j] = in[j], in[i]
			}
		}
	}
}
EOF

cat > /app/internal/plugins/compat.go <<'EOF'
package plugins

import (
	"bufio"
	"os"
	"strconv"
	"strings"
)

type Request struct {
	ID       string
	Version  string
	MinMajor int
	MinMinor int
	HasMin   bool
}

var defaults = map[string][2]int{
	"com.meshgrid.wireloom":      {8, 7},
	"com.meshgrid.depknit":       {8, 8},
	"com.meshgrid.artifactseal":  {8, 10},
	"com.meshgrid.pluginbridge":  {8, 5},
	"com.meshgrid.releasemesh":   {8, 9},
	"com.meshgrid.cataloghub":    {8, 10},
	"org.gradle.publish-offline": {8, 6},
}

func LoadRequests(path string) ([]Request, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var reqs []Request
	var cur *Request
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if line == "[[plugins]]" {
			if cur != nil {
				reqs = append(reqs, *cur)
			}
			cur = &Request{}
			continue
		}
		if cur == nil {
			continue
		}
		k, v, ok := splitKV(line)
		if !ok {
			continue
		}
		v = strings.Trim(v, `"`)
		switch k {
		case "id":
			cur.ID = v
		case "version":
			cur.Version = v
		case "min_gradle":
			maj, min, ok := parseMajMin(v)
			if ok {
				cur.MinMajor = maj
				cur.MinMinor = min
				cur.HasMin = true
			}
		}
	}
	if cur != nil {
		reqs = append(reqs, *cur)
	}
	return reqs, sc.Err()
}

func splitKV(line string) (string, string, bool) {
	idx := strings.Index(line, "=")
	if idx < 0 {
		return "", "", false
	}
	return strings.TrimSpace(line[:idx]), strings.TrimSpace(line[idx+1:]), true
}

func parseMajMin(s string) (int, int, bool) {
	parts := strings.Split(s, ".")
	if len(parts) != 2 {
		return 0, 0, false
	}
	a, err1 := strconv.Atoi(parts[0])
	b, err2 := strconv.Atoi(parts[1])
	if err1 != nil || err2 != nil {
		return 0, 0, false
	}
	return a, b, true
}

func Incompatible(req Request, gradleMajor, gradleMinor int) bool {
	minMaj, minMin := 0, 0
	if req.HasMin {
		minMaj, minMin = req.MinMajor, req.MinMinor
	} else if d, ok := defaults[req.ID]; ok {
		minMaj, minMin = d[0], d[1]
	} else {
		return false
	}
	if gradleMajor < minMaj {
		return true
	}
	if gradleMajor > minMaj {
		return false
	}
	return gradleMinor < minMin
}
EOF

cat > /app/internal/locks/decode.go <<'EOF'
package locks

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"strconv"
	"strings"
)

type Stats struct {
	FormatVersion   int
	RecordsTotal    int
	RecordsValid    int
	RecordsRejected int
	DupCoordRejects int
	PayloadBytes    int
}

type Record struct {
	Coordinate string
	Version    string
	Checksum   string
	Optional   bool
}

func Decode(path string) ([]Record, Stats, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, Stats{}, err
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	stats := Stats{}
	if !sc.Scan() || sc.Text() != "LOCK1" {
		return nil, stats, fmt.Errorf("bad magic")
	}
	if !sc.Scan() {
		return nil, stats, fmt.Errorf("missing version")
	}
	ver, err := strconv.Atoi(strings.TrimSpace(sc.Text()))
	if err != nil {
		return nil, stats, err
	}
	stats.FormatVersion = ver
	if ver != 1 {
		return nil, stats, fmt.Errorf("unsupported format")
	}
	if !sc.Scan() {
		return nil, stats, fmt.Errorf("missing count")
	}
	_, _ = strconv.Atoi(strings.TrimSpace(sc.Text()))

	seen := map[string]struct{}{}
	out := []Record{}
	for sc.Scan() {
		line := sc.Text()
		if strings.TrimSpace(line) == "" {
			continue
		}
		stats.RecordsTotal++
		parts := strings.Split(line, "\t")
		if len(parts) != 4 {
			stats.RecordsRejected++
			continue
		}
		coord, version, checksum, opt := parts[0], parts[1], parts[2], parts[3]
		reason := ""
		if opt != "0" && opt != "1" {
			reason = "BAD_OPTIONAL"
		} else if checksum != sha256Hex(coord, version) {
			reason = "BAD_CHECKSUM"
		} else if _, ok := seen[coord]; ok {
			reason = "DUP_COORD"
		}
		seen[coord] = struct{}{}
		if reason != "" {
			stats.RecordsRejected++
			if reason == "DUP_COORD" {
				stats.DupCoordRejects++
			}
			continue
		}
		rec := Record{Coordinate: coord, Version: version, Checksum: checksum, Optional: opt == "1"}
		out = append(out, rec)
		stats.RecordsValid++
		stats.PayloadBytes += len(line)
	}
	return out, stats, sc.Err()
}

func sha256Hex(coord, version string) string {
	sum := sha256.Sum256([]byte(coord + "|" + version))
	return hex.EncodeToString(sum[:])
}
EOF

cat > /app/internal/publish/offline.go <<'EOF'
package publish

import (
	"bufio"
	"os"
	"strings"
)

type Settings struct {
	RepositoriesMode string
	VaultPath        string
	SignedPublish    bool
}

func Load(path string) (Settings, error) {
	f, err := os.Open(path)
	if err != nil {
		return Settings{}, err
	}
	defer f.Close()
	s := Settings{}
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		idx := strings.Index(line, "=")
		if idx < 0 {
			continue
		}
		k := strings.TrimSpace(line[:idx])
		v := strings.Trim(strings.TrimSpace(line[idx+1:]), `"`)
		switch k {
		case "repositories_mode":
			s.RepositoriesMode = v
		case "vault_path":
			s.VaultPath = v
		case "signed_publish":
			s.SignedPublish = v == "true"
		}
	}
	return s, sc.Err()
}

type Issue struct {
	Kind     string
	EntityID string
	Detail   string
}

func Check(s Settings, requireOffline, failOnProject bool) []Issue {
	out := []Issue{}
	if failOnProject && s.RepositoriesMode != "FAIL_ON_PROJECT_REPOS" {
		out = append(out, Issue{Kind: "PROJECT_REPO_FORBIDDEN", EntityID: "repositories_mode", Detail: s.RepositoriesMode})
	}
	if requireOffline {
		if s.VaultPath != "/app/meshgrid/offline-vault" {
			out = append(out, Issue{Kind: "OFFLINE_REPO_MISCONFIG", EntityID: "vault_path", Detail: s.VaultPath})
		}
		if !s.SignedPublish {
			out = append(out, Issue{Kind: "PUBLISH_UNSIGNED", EntityID: "signed_publish", Detail: ""})
		}
	}
	return out
}
EOF

cat > /app/internal/mesh/analyze.go <<'EOF'
package mesh

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"

	"meshgridfix/internal/catalog"
	"meshgridfix/internal/locks"
	"meshgridfix/internal/plugins"
	"meshgridfix/internal/publish"
)

type Manifest struct {
	GradleMajor         int                    `json:"gradle_major"`
	GradleMinor         int                    `json:"gradle_minor"`
	Modules             []string               `json:"modules"`
	RequireOfflineVault bool                   `json:"require_offline_vault"`
	FailOnProjectRepos   bool                   `json:"fail_on_project_repos"`
	MaxDirectDeps       int                    `json:"max_direct_deps"`
	StrictBOM           bool                   `json:"strict_bom"`
	PolicyOverrides     map[string]interface{} `json:"policy_overrides"`
}

type ModuleFile struct {
	ModuleID         string            `json:"module_id"`
	Group            string            `json:"group"`
	Artifact         string            `json:"artifact"`
	Version          string            `json:"version"`
	BOMConsumer      bool              `json:"bom_consumer"`
	Dependencies     []string          `json:"dependencies"`
	LibraryAliases   []string          `json:"library_aliases"`
	VersionOverrides map[string]string `json:"version_overrides"`
}

type CaptureOut struct {
	FormatVersion   int `json:"format_version"`
	RecordsTotal    int `json:"records_total"`
	RecordsValid    int `json:"records_valid"`
	RecordsRejected int `json:"records_rejected"`
	DupCoordRejects int `json:"dup_coord_rejects"`
	PayloadBytes    int `json:"payload_bytes"`
}

type ModuleOut struct {
	ModuleID    string     `json:"module_id"`
	Coordinate  string     `json:"coordinate"`
	BOMConsumer bool       `json:"bom_consumer"`
	DirectDeps  []string   `json:"direct_deps"`
	Capture     CaptureOut `json:"capture"`
	Status      string     `json:"status"`
}

type Finding struct {
	FindingID string `json:"finding_id"`
	ModuleID  string `json:"module_id"`
	EntityID  string `json:"entity_id"`
	Kind      string `json:"kind"`
	EventSeq  int    `json:"event_seq"`
	Detail    string `json:"detail"`
}

type WorkspaceOut struct {
	GradleMajor         int  `json:"gradle_major"`
	GradleMinor         int  `json:"gradle_minor"`
	ModuleCount         int  `json:"module_count"`
	RequireOfflineVault bool `json:"require_offline_vault"`
	FailOnProjectRepos   bool `json:"fail_on_project_repos"`
	MaxDirectDeps       int  `json:"max_direct_deps"`
	StrictBOM           bool `json:"strict_bom"`
}

type Report struct {
	Workspace               WorkspaceOut `json:"workspace"`
	Modules                 []ModuleOut  `json:"modules"`
	Findings                []Finding    `json:"findings"`
	DuplicateModulesSkipped int          `json:"duplicate_modules_skipped"`
	Status                  string       `json:"status"`
}

func Analyze(root string) (*Report, error) {
	man, err := loadManifest(filepath.Join(root, "workspace.manifest.json"))
	if err != nil {
		return nil, err
	}
	requireOffline, failOnProject, maxDeps, strictBOM := resolvePolicy(man)

	cat, err := catalog.Load(filepath.Join(root, "catalog", "libs.versions.toml"))
	if err != nil {
		return nil, err
	}
	reqs, err := plugins.LoadRequests(filepath.Join(root, "plugins", "plugin-requests.toml"))
	if err != nil {
		return nil, err
	}
	pub, err := publish.Load(filepath.Join(root, "publish", "offline-vault.toml"))
	if err != nil {
		return nil, err
	}

	findings := []Finding{}
	for _, req := range reqs {
		if plugins.Incompatible(req, man.GradleMajor, man.GradleMinor) {
			findings = append(findings, Finding{
				FindingID: fid("meshgrid", req.ID, "PLUGIN_INCOMPATIBLE", 0),
				ModuleID:  "meshgrid",
				EntityID:  req.ID,
				Kind:      "PLUGIN_INCOMPATIBLE",
				EventSeq:  0,
				Detail:    req.Version,
			})
		}
	}

	for _, alias := range catalog.AliasConflicts(cat) {
		findings = append(findings, Finding{
			FindingID: fid("meshgrid", alias, "CATALOG_ALIAS_CONFLICT", 0),
			ModuleID:  "meshgrid",
			EntityID:  alias,
			Kind:      "CATALOG_ALIAS_CONFLICT",
			EventSeq:  0,
			Detail:    "bundle",
		})
	}

	for _, alias := range catalog.InlineDrifts(cat) {
		lib := cat.Libraries[alias]
		findings = append(findings, Finding{
			FindingID: fid("meshgrid", alias, "CATALOG_VERSION_DRIFT", 0),
			ModuleID:  "meshgrid",
			EntityID:  alias,
			Kind:      "CATALOG_VERSION_DRIFT",
			EventSeq:  0,
			Detail:    lib.Version,
		})
	}

	for _, issue := range publish.Check(pub, requireOffline, failOnProject) {
		findings = append(findings, Finding{
			FindingID: fid("meshgrid", issue.EntityID, issue.Kind, 0),
			ModuleID:  "meshgrid",
			EntityID:  issue.EntityID,
			Kind:      issue.Kind,
			EventSeq:  0,
			Detail:    issue.Detail,
		})
	}

	seenMod := map[string]struct{}{}
	dupSkipped := 0
	maxOrd := -1
	loaded := map[string]*ModuleFile{}
	moduleOrder := []string{}
	coords := map[string]string{}
	moduleFindingCount := map[string]int{}
	captures := map[string]CaptureOut{}

	for ord, mid := range man.Modules {
		if ord > maxOrd {
			maxOrd = ord
		}
		if _, ok := seenMod[mid]; ok {
			dupSkipped++
			continue
		}
		seenMod[mid] = struct{}{}
		moduleOrder = append(moduleOrder, mid)

		mf, err := loadModule(filepath.Join(root, "modules", mid+".module.json"))
		if err != nil {
			return nil, err
		}
		loaded[mid] = mf

		coord := mf.Group + ":" + mf.Artifact
		if prev, ok := coords[coord]; ok {
			findings = append(findings, Finding{
				FindingID: fid(mid, coord, "DUPLICATE_MODULE_COORDINATE", ord),
				ModuleID:  mid,
				EntityID:  coord,
				Kind:      "DUPLICATE_MODULE_COORDINATE",
				EventSeq:  ord,
				Detail:    prev,
			})
			moduleFindingCount[mid]++
		} else {
			coords[coord] = mid
		}

		for _, dep := range mf.Dependencies {
			if dep == mid {
				findings = append(findings, Finding{
					FindingID: fid(mid, mid, "SELF_DEPENDENCY", ord),
					ModuleID:  mid,
					EntityID:  mid,
					Kind:      "SELF_DEPENDENCY",
					EventSeq:  ord,
					Detail:    "",
				})
				moduleFindingCount[mid]++
			}
		}

		if len(mf.Dependencies) > maxDeps {
			findings = append(findings, Finding{
				FindingID: fid(mid, mid, "DEPENDENCY_FANOUT", ord),
				ModuleID:  mid,
				EntityID:  mid,
				Kind:      "DEPENDENCY_FANOUT",
				EventSeq:  ord,
				Detail:    strconv.Itoa(len(mf.Dependencies)),
			})
			moduleFindingCount[mid]++
		}

		if strictBOM && mf.BOMConsumer && len(mf.VersionOverrides) > 0 {
			keys := make([]string, 0, len(mf.VersionOverrides))
			for k := range mf.VersionOverrides {
				keys = append(keys, k)
			}
			sort.Strings(keys)
			k := keys[0]
			findings = append(findings, Finding{
				FindingID: fid(mid, k, "BOM_OVERRIDE_FORBIDDEN", ord),
				ModuleID:  mid,
				EntityID:  k,
				Kind:      "BOM_OVERRIDE_FORBIDDEN",
				EventSeq:  ord,
				Detail:    mf.VersionOverrides[k],
			})
			moduleFindingCount[mid]++
		}

		capOut := CaptureOut{}
		lockPath := filepath.Join(root, "locks", mid+".lock")
		recs, st, err := locks.Decode(lockPath)
		if err != nil {
			findings = append(findings, Finding{
				FindingID: fid(mid, mid, "LOCK_MISSING", ord),
				ModuleID:  mid,
				EntityID:  mid,
				Kind:      "LOCK_MISSING",
				EventSeq:  ord,
				Detail:    "",
			})
			moduleFindingCount[mid]++
		} else {
			capOut = CaptureOut{
				FormatVersion:   st.FormatVersion,
				RecordsTotal:    st.RecordsTotal,
				RecordsValid:    st.RecordsValid,
				RecordsRejected: st.RecordsRejected,
				DupCoordRejects: st.DupCoordRejects,
				PayloadBytes:    st.PayloadBytes,
			}
			refs := referencedCoords(mf, cat)
			for _, rec := range recs {
				if rec.Optional {
					continue
				}
				if exp, ok := refs[rec.Coordinate]; ok {
					if exp != rec.Version {
						findings = append(findings, Finding{
							FindingID: fid(mid, rec.Coordinate, "LOCK_VERSION_DRIFT", ord),
							ModuleID:  mid,
							EntityID:  rec.Coordinate,
							Kind:      "LOCK_VERSION_DRIFT",
							EventSeq:  ord,
							Detail:    rec.Version,
						})
						moduleFindingCount[mid]++
					}
				} else {
					findings = append(findings, Finding{
						FindingID: fid(mid, rec.Coordinate, "ORPHAN_LOCK_ENTRY", ord),
						ModuleID:  mid,
						EntityID:  rec.Coordinate,
						Kind:      "ORPHAN_LOCK_ENTRY",
						EventSeq:  ord,
						Detail:    "",
					})
					moduleFindingCount[mid]++
				}
			}
		}
		captures[mid] = capOut
	}

	for _, mid := range moduleOrder {
		mf := loaded[mid]
		ord := firstIndex(man.Modules, mid)
		for _, dep := range mf.Dependencies {
			if dep == mid {
				continue
			}
			if _, ok := loaded[dep]; !ok {
				findings = append(findings, Finding{
					FindingID: fid(mid, dep, "UNKNOWN_DEPENDENCY", ord),
					ModuleID:  mid,
					EntityID:  dep,
					Kind:      "UNKNOWN_DEPENDENCY",
					EventSeq:  ord,
					Detail:    "UNKNOWN_DEPENDENCY",
				})
				moduleFindingCount[mid]++
			}
		}
	}

	audit := maxOrd + 1
	cycleSucc := findCycleSuccessors(loaded)
	cycleMods := make([]string, 0, len(cycleSucc))
	for mid := range cycleSucc {
		cycleMods = append(cycleMods, mid)
	}
	sort.Strings(cycleMods)
	for _, mid := range cycleMods {
		findings = append(findings, Finding{
			FindingID: fid(mid, mid, "MODULE_CYCLE", audit),
			ModuleID:  mid,
			EntityID:  mid,
			Kind:      "MODULE_CYCLE",
			EventSeq:  audit,
			Detail:    cycleSucc[mid],
		})
		moduleFindingCount[mid]++
	}

	for _, ref := range catalog.UnresolvedRefs(cat) {
		findings = append(findings, Finding{
			FindingID: fid("meshgrid", ref, "CATALOG_UNRESOLVED_REF", audit),
			ModuleID:  "meshgrid",
			EntityID:  ref,
			Kind:      "CATALOG_UNRESOLVED_REF",
			EventSeq:  audit,
			Detail:    "",
		})
	}

	moduleOut := make([]ModuleOut, 0, len(moduleOrder))
	sortedIDs := append([]string{}, moduleOrder...)
	sort.Strings(sortedIDs)
	for _, mid := range sortedIDs {
		mf := loaded[mid]
		depsCopy := append([]string{}, mf.Dependencies...)
		sort.Strings(depsCopy)
		status := "STABLE"
		if moduleFindingCount[mid] > 0 {
			status = "DRIFT"
		}
		moduleOut = append(moduleOut, ModuleOut{
			ModuleID:    mid,
			Coordinate:  mf.Group + ":" + mf.Artifact + ":" + mf.Version,
			BOMConsumer: mf.BOMConsumer,
			DirectDeps:  depsCopy,
			Capture:     captures[mid],
			Status:      status,
		})
	}

	sort.Slice(findings, func(i, j int) bool { return findings[i].FindingID < findings[j].FindingID })

	status := "STABLE"
	if len(findings) > 0 {
		status = "DRIFT"
	}

	return &Report{
		Workspace: WorkspaceOut{
			GradleMajor:         man.GradleMajor,
			GradleMinor:         man.GradleMinor,
			ModuleCount:         len(moduleOut),
			RequireOfflineVault: requireOffline,
			FailOnProjectRepos:   failOnProject,
			MaxDirectDeps:       maxDeps,
			StrictBOM:           strictBOM,
		},
		Modules:                 moduleOut,
		Findings:                findings,
		DuplicateModulesSkipped: dupSkipped,
		Status:                  status,
	}, nil
}

func WriteReport(path string, rep *Report) error {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(rep); err != nil {
		return err
	}
	// Encode already adds trailing newline
	return os.WriteFile(path, buf.Bytes(), 0o644)
}

func resolvePolicy(man Manifest) (bool, bool, int, bool) {
	requireOffline := man.RequireOfflineVault
	failOnProject := man.FailOnProjectRepos
	maxDeps := man.MaxDirectDeps
	if maxDeps == 0 {
		maxDeps = 3
	}
	strictBOM := man.StrictBOM
	ov := man.PolicyOverrides
	if ov == nil {
		return requireOffline, failOnProject, maxDeps, strictBOM
	}
	if v, ok := ov["require_offline_vault"]; ok {
		if b, ok := v.(bool); ok {
			requireOffline = b
		}
	}
	if v, ok := ov["fail_on_project_repos"]; ok {
		if b, ok := v.(bool); ok {
			failOnProject = b
		}
	}
	if v, ok := ov["strict_bom"]; ok {
		if b, ok := v.(bool); ok {
			strictBOM = b
		}
	}
	if v, ok := ov["max_direct_deps"]; ok {
		switch n := v.(type) {
		case float64:
			maxDeps = int(n)
		case int:
			maxDeps = n
		}
	}
	return requireOffline, failOnProject, maxDeps, strictBOM
}

func loadManifest(path string) (Manifest, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return Manifest{}, err
	}
	var m Manifest
	if err := json.Unmarshal(b, &m); err != nil {
		return Manifest{}, err
	}
	return m, nil
}

func loadModule(path string) (*ModuleFile, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var m ModuleFile
	if err := json.Unmarshal(b, &m); err != nil {
		return nil, err
	}
	if m.VersionOverrides == nil {
		m.VersionOverrides = map[string]string{}
	}
	return &m, nil
}

func referencedCoords(mf *ModuleFile, cat *catalog.Catalog) map[string]string {
	out := map[string]string{}
	for _, alias := range mf.LibraryAliases {
		lib, ok := cat.Libraries[alias]
		if !ok {
			continue
		}
		ver, _, ok := catalog.ResolveLibraryVersion(cat, lib)
		if !ok {
			continue
		}
		out[lib.Module] = ver
	}
	for k, v := range mf.VersionOverrides {
		out[k] = v
	}
	return out
}

func findCycleSuccessors(loaded map[string]*ModuleFile) map[string]string {
	nodes := make([]string, 0, len(loaded))
	for mid := range loaded {
		nodes = append(nodes, mid)
	}
	sort.Strings(nodes)
	inCycle := map[string]bool{}
	for _, start := range nodes {
		visited := map[string]bool{}
		var dfs func(string, []string) bool
		dfs = func(cur string, path []string) bool {
			for i, p := range path {
				if p == cur {
					for _, n := range path[i:] {
						inCycle[n] = true
					}
					inCycle[cur] = true
					return true
				}
			}
			if visited[cur] {
				return false
			}
			visited[cur] = true
			mf := loaded[cur]
			if mf == nil {
				return false
			}
			for _, dep := range mf.Dependencies {
				if _, ok := loaded[dep]; !ok {
					continue
				}
				if dfs(dep, append(path, cur)) {
					return true
				}
			}
			return false
		}
		dfs(start, nil)
	}
	out := map[string]string{}
	for mid := range inCycle {
		mf := loaded[mid]
		cands := []string{}
		for _, dep := range mf.Dependencies {
			if inCycle[dep] {
				cands = append(cands, dep)
			}
		}
		sort.Strings(cands)
		if len(cands) > 0 {
			out[mid] = cands[0]
		}
	}
	return out
}

func fid(mid, entity, kind string, seq int) string {
	return fmt.Sprintf("%s::%s::%s::%04d", mid, entity, kind, seq)
}

func firstIndex(list []string, mid string) int {
	for i, v := range list {
		if v == mid {
			return i
		}
	}
	return 0
}
EOF

make -C /app build
/app/build/gridknit
