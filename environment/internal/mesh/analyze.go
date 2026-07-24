package mesh

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"

	"meshgridfix/internal/catalog"
	"meshgridfix/internal/locks"
	"meshgridfix/internal/plugins"
	"meshgridfix/internal/publish"
)

type Manifest struct {
	GradleMajor          int                    `json:"gradle_major"`
	GradleMinor          int                    `json:"gradle_minor"`
	Modules              []string               `json:"modules"`
	RequireOfflineVault  bool                   `json:"require_offline_vault"`
	FailOnProjectRepos    bool                   `json:"fail_on_project_repos"`
	MaxDirectDeps        int                    `json:"max_direct_deps"`
	StrictBOM            bool                   `json:"strict_bom"`
	PolicyOverrides      map[string]interface{} `json:"policy_overrides"`
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
				FindingID: fid("meshgrid", req.ID, 0),
				ModuleID:  "meshgrid",
				EntityID:  req.ID,
				Kind:      "PLUGIN_INCOMPATIBLE",
				EventSeq:  0,
				Detail:    req.Version,
			})
		}
	}

	// BUG: alias conflict detail wrong and missing kind sometimes skipped
	for _, alias := range catalog.AliasConflicts(cat) {
		findings = append(findings, Finding{
			FindingID: fid("meshgrid", alias, 0),
			ModuleID:  "meshgrid",
			EntityID:  alias,
			Kind:      "CATALOG_ALIAS_CONFLICT",
			EventSeq:  0,
			Detail:    "library",
		})
	}

	for name, lib := range cat.Libraries {
		if lib.Inline {
			if refVer, ok := cat.Versions[strings.TrimSuffix(name, "")]; ok && refVer != lib.Version {
				_ = refVer
			}
			// BUG: never emits CATALOG_VERSION_DRIFT for inline libs that disagree with matching version key
			if v, ok := cat.Versions[name]; ok && v != lib.Version {
				_ = v
			}
		}
		if lib.VersionRef != "" {
			if _, ok := cat.Versions[lib.VersionRef]; !ok {
				// BUG: skip unresolved refs here; should be post-mesh
			}
		}
	}

	for _, pair := range publish.Check(pub, requireOffline, failOnProject) {
		findings = append(findings, Finding{
			FindingID: fid("meshgrid", pair[0], 0),
			ModuleID:  "meshgrid",
			EntityID:  pair[0],
			Kind:      pair[0],
			EventSeq:  0,
			Detail:    pair[1],
		})
	}

	seenMod := map[string]struct{}{}
	dupSkipped := 0
	maxOrd := -1
	loaded := map[string]*ModuleFile{}
	moduleOut := []ModuleOut{}
	coords := map[string]string{}
	moduleFindings := map[string]int{}

	for ord, mid := range man.Modules {
		if ord > maxOrd {
			maxOrd = ord
		}
		// BUG: empty module id not treated as identity / skipped incorrectly
		if mid != "" {
			if _, ok := seenMod[mid]; ok {
				dupSkipped++
				continue
			}
		}
		seenMod[mid] = struct{}{}

		mf, err := loadModule(filepath.Join(root, "modules", mid+".module.json"))
		if err != nil {
			return nil, err
		}
		loaded[mid] = mf

		coord := mf.Group + ":" + mf.Artifact
		if prev, ok := coords[coord]; ok {
			findings = append(findings, Finding{
				FindingID: fid(mid, coord, ord),
				ModuleID:  mid,
				EntityID:  coord,
				Kind:      "DUPLICATE_MODULE_COORDINATE",
				EventSeq:  ord,
				Detail:    prev,
			})
			moduleFindings[mid]++
		} else {
			coords[coord] = mid
		}

		for _, dep := range mf.Dependencies {
			if dep == mid {
				findings = append(findings, Finding{
					FindingID: fid(mid, mid, ord),
					ModuleID:  mid,
					EntityID:  mid,
					Kind:      "SELF_DEPENDENCY",
					EventSeq:  ord,
					Detail:    "",
				})
				moduleFindings[mid]++
			}
		}
		// BUG: fanout uses >= instead of >
		if len(mf.Dependencies) >= maxDeps {
			findings = append(findings, Finding{
				FindingID: fid(mid, mid, ord),
				ModuleID:  mid,
				EntityID:  mid,
				Kind:      "DEPENDENCY_FANOUT",
				EventSeq:  ord,
				Detail:    strconv.Itoa(len(mf.Dependencies)),
			})
			moduleFindings[mid]++
		}

		if strictBOM && mf.BOMConsumer && len(mf.VersionOverrides) > 0 {
			keys := make([]string, 0, len(mf.VersionOverrides))
			for k := range mf.VersionOverrides {
				keys = append(keys, k)
			}
			sort.Strings(keys)
			// BUG: uses last key instead of first
			k := keys[len(keys)-1]
			findings = append(findings, Finding{
				FindingID: fid(mid, k, ord),
				ModuleID:  mid,
				EntityID:  k,
				Kind:      "BOM_OVERRIDE_FORBIDDEN",
				EventSeq:  ord,
				Detail:    mf.VersionOverrides[k],
			})
			moduleFindings[mid]++
		}

		capOut := CaptureOut{}
		lockPath := filepath.Join(root, "locks", mid+".lock")
		recs, st, err := locks.Decode(lockPath)
		if err != nil {
			findings = append(findings, Finding{
				FindingID: fid(mid, mid, ord),
				ModuleID:  mid,
				EntityID:  mid,
				Kind:      "LOCK_MISSING",
				EventSeq:  ord,
				Detail:    "",
			})
			moduleFindings[mid]++
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
				if !rec.Optional {
					if exp, ok := refs[rec.Coordinate]; ok && exp != rec.Version {
						findings = append(findings, Finding{
							FindingID: fid(mid, rec.Coordinate, ord),
							ModuleID:  mid,
							EntityID:  rec.Coordinate,
							Kind:      "LOCK_VERSION_DRIFT",
							EventSeq:  ord,
							Detail:    rec.Version,
						})
						moduleFindings[mid]++
					}
					if _, ok := refs[rec.Coordinate]; !ok {
						findings = append(findings, Finding{
							FindingID: fid(mid, rec.Coordinate, ord),
							ModuleID:  mid,
							EntityID:  rec.Coordinate,
							Kind:      "ORPHAN_LOCK_ENTRY",
							EventSeq:  ord,
							Detail:    "",
						})
						moduleFindings[mid]++
					}
				}
			}
		}

		depsCopy := append([]string{}, mf.Dependencies...)
		sort.Strings(depsCopy)
		status := "STABLE"
		if moduleFindings[mid] > 0 {
			status = "DRIFT"
		}
		moduleOut = append(moduleOut, ModuleOut{
			ModuleID:    mid,
			Coordinate:  mf.Group + ":" + mf.Artifact + ":" + mf.Version,
			BOMConsumer: mf.BOMConsumer,
			DirectDeps:  depsCopy,
			Capture:     capOut,
			Status:      status,
		})
	}

	// unknown deps after load
	for mid, mf := range loaded {
		ord := indexOf(man.Modules, mid)
		for _, dep := range mf.Dependencies {
			if dep == mid {
				continue
			}
			if _, ok := loaded[dep]; !ok {
				findings = append(findings, Finding{
					FindingID: fid(mid, dep, ord),
					ModuleID:  mid,
					EntityID:  dep,
					Kind:      "UNKNOWN_DEPENDENCY",
					EventSeq:  ord,
					Detail:    "UNKNOWN_DEPENDENCY",
				})
				moduleFindings[mid]++
			}
		}
	}

	// BUG: cycle detection only checks mutual direct edges, not longer cycles
	audit := maxOrd // BUG: should be maxOrd+1
	for mid, mf := range loaded {
		for _, dep := range mf.Dependencies {
			if other, ok := loaded[dep]; ok {
				for _, back := range other.Dependencies {
					if back == mid {
						succ := dep
						if mid < dep {
							succ = dep
						} else {
							succ = mid
						}
						_ = succ
						findings = append(findings, Finding{
							FindingID: fid(mid, mid, audit),
							ModuleID:  mid,
							EntityID:  mid,
							Kind:      "MODULE_CYCLE",
							EventSeq:  audit,
							Detail:    dep,
						})
						moduleFindings[mid]++
					}
				}
			}
		}
	}

	// post unresolved refs missing
	sort.Slice(moduleOut, func(i, j int) bool { return moduleOut[i].ModuleID < moduleOut[j].ModuleID })
	// BUG: descending findings sort
	sort.Slice(findings, func(i, j int) bool { return findings[i].FindingID > findings[j].FindingID })

	for i := range moduleOut {
		if moduleFindings[moduleOut[i].ModuleID] > 0 {
			moduleOut[i].Status = "DRIFT"
		} else {
			moduleOut[i].Status = "STABLE"
		}
	}

	status := "STABLE"
	if len(findings) > 0 {
		status = "DRIFT"
	}
	// BUG: invert root status sometimes when findings exist → STABLE wrongly if we set VALID-like
	_ = status

	rep := &Report{
		Workspace: WorkspaceOut{
			GradleMajor:         man.GradleMajor,
			GradleMinor:         man.GradleMinor,
			ModuleCount:         len(man.Modules), // BUG: raw manifest length; must be unique post-dedup count
			RequireOfflineVault: requireOffline,
			FailOnProjectRepos:   failOnProject,
			MaxDirectDeps:       maxDeps,
			StrictBOM:           strictBOM,
		},
		Modules:                 moduleOut,
		Findings:                findings,
		DuplicateModulesSkipped: dupSkipped,
		Status:                  "STABLE", // BUG: always STABLE
	}
	return rep, nil
}

func WriteReport(path string, rep *Report) error {
	// BUG: pretty JSON without trailing newline guarantee via MarshalIndent
	b, err := json.MarshalIndent(rep, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, b, 0o644)
}

func resolvePolicy(man Manifest) (bool, bool, int, bool) {
	requireOffline := man.RequireOfflineVault
	failOnProject := man.FailOnProjectRepos
	maxDeps := man.MaxDirectDeps
	if maxDeps == 0 {
		maxDeps = 3
	}
	strictBOM := man.StrictBOM
	// default strictBOM true when absent — JSON false is fine
	if man.PolicyOverrides == nil {
		return requireOffline, failOnProject, maxDeps, strictBOM
	}
	ov := man.PolicyOverrides
	// BUG: invert booleans and rescale ints
	if v, ok := ov["require_offline_vault"]; ok {
		if b, ok := v.(bool); ok {
			requireOffline = !b
		}
	}
	if v, ok := ov["fail_on_project_repos"]; ok {
		if b, ok := v.(bool); ok {
			failOnProject = !b
		}
	}
	if v, ok := ov["strict_bom"]; ok {
		if b, ok := v.(bool); ok {
			strictBOM = !b
		}
	}
	if v, ok := ov["max_direct_deps"]; ok {
		switch n := v.(type) {
		case float64:
			maxDeps = int(n) + 1
		case int:
			maxDeps = n + 1
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
	if !m.StrictBOM && m.PolicyOverrides == nil {
		// leave as decoded; zero value false — tests expect true default via explicit true in fixture
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
	// BUG: apply overrides first then let catalog aliases overwrite (aliases must not win).
	for k, v := range mf.VersionOverrides {
		out[k] = v
	}
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
	return out
}

func fid(mid, entity string, seq int) string {
	// BUG: missing kind segment; policy requires module::entity::kind::seq
	return fmt.Sprintf("%s::%s::%04d", mid, entity, seq)
}

func indexOf(list []string, mid string) int {
	for i, v := range list {
		if v == mid {
			return i
		}
	}
	return 0
}
