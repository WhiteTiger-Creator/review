package mesh

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"

	"meshgrid.fix/internal/catalog"
	"meshgrid.fix/internal/locks"
	"meshgrid.fix/internal/plugins"
	"meshgrid.fix/internal/publish"
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

		if len(mf.Dependencies) >= maxDeps {
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
			k := keys[len(keys)-1]
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
				RecordsValid:    st.RecordsRejected,
				RecordsRejected: st.RecordsValid,
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

	audit := maxOrd
	for mid, mf := range loaded {
		for _, dep := range mf.Dependencies {
			if other, ok := loaded[dep]; ok {
				for _, back := range other.Dependencies {
					if back == mid {
						findings = append(findings, Finding{
							FindingID: fid(mid, mid, "MODULE_CYCLE", audit),
							ModuleID:  mid,
							EntityID:  mid,
							Kind:      "MODULE_CYCLE",
							EventSeq:  audit,
							Detail:    dep,
						})
						moduleFindingCount[mid]++
					}
				}
			}
		}
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

func fid(mid, entity, kind string, seq int) string {
	return fmt.Sprintf("%s::%s::%s::%04d", mid, kind, entity, seq)
}

func firstIndex(list []string, mid string) int {
	for i, v := range list {
		if v == mid {
			return i
		}
	}
	return 0
}
