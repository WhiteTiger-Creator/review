package audit

import (
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "fmt"
    "os"
    "path/filepath"
    "sort"
    "strings"
)

const (
    ExpectedSocketPath = "/run/telemetry/collector.sock"
    ExpectedOwner      = "collector-sink"
    ExpectedMode       = "0660"
)

type State struct {
    Root              string
    SocketUnitPresent bool
    ListenStream      string
    SocketUser        string
    SocketGroup       string
    SocketMode        string
    ServiceSockets    string
    ServiceSocketMode string
    ConfigBindPath    string
    ConfigRunUser     string
    ConfigSinkOwner   string
    TmpDirMode        string
    TmpDirOwner       string
    TmpDirGroup       string
    TmpSocketMode     string
    TmpSocketOwner    string
    TmpSocketGroup    string
    SourceDigest      string
}

type Report struct {
    OK        bool              `json:"ok"`
    Root      string            `json:"root"`
    Runtime   RuntimeView       `json:"runtime"`
    Manifest  ManifestView      `json:"manifest"`
    Lifecycle []LifecyclePhase  `json:"lifecycle"`
    Checks    map[string]bool   `json:"checks"`
    Notes     []string          `json:"notes"`
    Digest    string            `json:"report_digest"`
}

type RuntimeView struct {
    Authority         string `json:"authority"`
    SocketPath        string `json:"socket_path"`
    SocketOwner       string `json:"socket_owner"`
    SocketGroup       string `json:"socket_group"`
    SocketMode        string `json:"socket_mode"`
    ServiceSockets    string `json:"service_sockets"`
    ServiceSocketMode string `json:"service_socket_mode"`
}

type ManifestView struct {
    Path       string            `json:"path"`
    Values     map[string]string `json:"values"`
    Consistent bool              `json:"consistent"`
    Provenance string            `json:"provenance"`
}

type LifecyclePhase struct {
    Phase       string `json:"phase"`
    Authority   string `json:"authority"`
    SocketPath  string `json:"socket_path"`
    SocketOwner string `json:"socket_owner"`
    SocketGroup string `json:"socket_group"`
    SocketMode  string `json:"socket_mode"`
    SocketInode string `json:"socket_inode"`
}

type Trace struct {
    Root           string           `json:"root"`
    RuntimeSocket  RuntimeView      `json:"runtime_socket"`
    AuthorityTrace []AuthorityTrace `json:"authority_trace"`
    Phases         []LifecyclePhase `json:"phases"`
    StableInode    bool             `json:"stable_inode"`
}

type AuthorityTrace struct {
    Source    string `json:"source"`
    Authority string `json:"authority"`
    Path      string `json:"path"`
    Owner     string `json:"owner"`
    Mode      string `json:"mode"`
}

func LoadState(root string) (State, error) {
    abs, err := filepath.Abs(root)
    if err != nil {
        return State{}, err
    }
    state := State{Root: abs}
    socketPath := filepath.Join(abs, "systemd", "collector.socket")
    if _, err := os.Stat(socketPath); err == nil {
        state.SocketUnitPresent = true
        unit, err := parseKeyValueFile(socketPath)
        if err != nil {
            return State{}, err
        }
        state.ListenStream = strings.TrimSpace(unit["ListenStream"])
        state.SocketUser = strings.TrimSpace(unit["SocketUser"])
        state.SocketGroup = strings.TrimSpace(unit["SocketGroup"])
        state.SocketMode = normalizeMode(unit["SocketMode"])
    } else if !os.IsNotExist(err) {
        return State{}, err
    }

    servicePath := filepath.Join(abs, "systemd", "collector.service")
    if service, err := parseKeyValueFile(servicePath); err == nil {
        state.ServiceSockets = strings.TrimSpace(service["Sockets"])
        env := parseEnvironment(service["Environment"])
        state.ServiceSocketMode = strings.TrimSpace(env["COLLECTOR_SOCKET_MODE"])
        if state.ServiceSocketMode == "" {
            state.ServiceSocketMode = extractFlag(service["ExecStart"], "--socket-mode")
        }
    } else {
        return State{}, err
    }

    yamlPath := filepath.Join(abs, "etc", "collector", "collector.yaml")
    yaml, err := parseSimpleYAML(yamlPath)
    if err != nil {
        return State{}, err
    }
    state.ConfigBindPath = strings.TrimSpace(yaml["bind_path"])
    state.ConfigRunUser = strings.TrimSpace(yaml["run_user"])
    state.ConfigSinkOwner = strings.TrimSpace(yaml["sink_owner"])

    tmpPath := filepath.Join(abs, "etc", "tmpfiles.d", "collector.conf")
    tmp, err := parseTmpfiles(tmpPath)
    if err != nil {
        return State{}, err
    }
    if dir, ok := tmp["/run/telemetry"]; ok {
        state.TmpDirMode = normalizeMode(dir.Mode)
        state.TmpDirOwner = dir.User
        state.TmpDirGroup = dir.Group
    }
    if sock, ok := tmp[ExpectedSocketPath]; ok {
        state.TmpSocketMode = normalizeMode(sock.Mode)
        state.TmpSocketOwner = sock.User
        state.TmpSocketGroup = sock.Group
    }
    if state.TmpSocketOwner == "" && state.ConfigBindPath != "" {
        if legacy, ok := tmp[state.ConfigBindPath]; ok {
            state.TmpSocketMode = normalizeMode(legacy.Mode)
            state.TmpSocketOwner = legacy.User
            state.TmpSocketGroup = legacy.Group
        }
    }

    digest, err := sourceDigest(abs, []string{
        "systemd/collector.socket",
        "systemd/collector.service",
        "etc/collector/collector.yaml",
        "etc/tmpfiles.d/collector.conf",
    })
    if err != nil {
        return State{}, err
    }
    state.SourceDigest = digest
    return state, nil
}

func Runtime(state State) RuntimeView {
    if state.SocketUnitPresent && state.ServiceSockets == "collector.socket" && state.ServiceSocketMode == "systemd" {
        return RuntimeView{
            Authority:         "systemd",
            SocketPath:        state.ListenStream,
            SocketOwner:       state.SocketUser,
            SocketGroup:       state.SocketGroup,
            SocketMode:        state.SocketMode,
            ServiceSockets:    state.ServiceSockets,
            ServiceSocketMode: state.ServiceSocketMode,
        }
    }
    owner := state.ConfigSinkOwner
    if owner == "" {
        owner = state.ConfigRunUser
    }
    return RuntimeView{
        Authority:         "collector.yaml",
        SocketPath:        state.ConfigBindPath,
        SocketOwner:       owner,
        SocketGroup:       owner,
        SocketMode:        state.TmpSocketMode,
        ServiceSockets:    state.ServiceSockets,
        ServiceSocketMode: state.ServiceSocketMode,
    }
}

func ManifestValues(state State) map[string]string {
    authority := "collector.yaml"
    socketPath := state.ConfigBindPath
    socketOwner := state.ConfigSinkOwner
    socketGroup := state.ConfigSinkOwner
    socketMode := state.TmpSocketMode
    if state.SocketUnitPresent {
        authority = "systemd"
        socketPath = state.ListenStream
        socketOwner = state.SocketUser
        socketGroup = state.SocketGroup
        socketMode = state.SocketMode
    }
    return map[string]string{
        "schema":                 "telemetry.collector.exporter.v2",
        "authority":              authority,
        "socket_path":            socketPath,
        "socket_user":            socketOwner,
        "socket_group":           socketGroup,
        "socket_mode":            normalizeMode(socketMode),
        "service_socket":         state.ServiceSockets,
        "service_socket_mode":    state.ServiceSocketMode,
        "tmpfiles_dir_owner":     state.TmpDirOwner,
        "tmpfiles_dir_group":     state.TmpDirGroup,
        "tmpfiles_socket_owner":  state.TmpSocketOwner,
        "tmpfiles_socket_group":  state.TmpSocketGroup,
        "tmpfiles_socket_mode":   normalizeMode(state.TmpSocketMode),
        "config_fallback_path":   state.ConfigBindPath,
        "config_run_user":        state.ConfigRunUser,
        "sink_owner":             state.ConfigSinkOwner,
        "source_digest":          state.SourceDigest,
        "provenance":             "regenerated-from-visible-authorities",
    }
}

func FormatManifest(values map[string]string) string {
    keys := []string{
        "schema", "authority", "socket_path", "socket_user", "socket_group", "socket_mode",
        "service_socket", "service_socket_mode", "tmpfiles_dir_owner", "tmpfiles_dir_group",
        "tmpfiles_socket_owner", "tmpfiles_socket_group", "tmpfiles_socket_mode",
        "config_fallback_path", "config_run_user", "sink_owner", "source_digest", "provenance",
    }
    var b strings.Builder
    for _, key := range keys {
        b.WriteString(key)
        b.WriteString("=")
        b.WriteString(values[key])
        b.WriteString("\n")
    }
    return b.String()
}

func WriteManifest(root, outPath string) error {
    state, err := LoadState(root)
    if err != nil {
        return err
    }
    if outPath == "" {
        outPath = filepath.Join(root, "generated", "exporter.manifest")
    }
    if err := os.MkdirAll(filepath.Dir(outPath), 0o755); err != nil {
        return err
    }
    return os.WriteFile(outPath, []byte(FormatManifest(ManifestValues(state))), 0o644)
}

func BuildReport(root, reportPath, tracePath string) (Report, error) {
    state, err := LoadState(root)
    if err != nil {
        return Report{}, err
    }
    manifestPath := filepath.Join(root, "generated", "exporter.manifest")
    if _, err := os.Stat(manifestPath); os.IsNotExist(err) {
        if err := WriteManifest(root, manifestPath); err != nil {
            return Report{}, err
        }
    }
    manifest, err := parseManifest(manifestPath)
    if err != nil {
        return Report{}, err
    }
    expected := ManifestValues(state)
    consistent := mapsEqual(expected, manifest)
    runtime := Runtime(state)
    phases := lifecycle(runtime)
    stable := sameInode(phases)

    checks := map[string]bool{
        "generated_manifest_current":       consistent,
        "runtime_socket_matches_manifest":  runtime.Authority == manifest["authority"] && runtime.SocketPath == manifest["socket_path"],
        "socket_owned_by_collector_sink":   runtime.SocketOwner == ExpectedOwner && runtime.SocketGroup == ExpectedOwner,
        "tmpfiles_preserve_socket_owner":   state.TmpSocketOwner == runtime.SocketOwner && state.TmpSocketGroup == runtime.SocketGroup && normalizeMode(state.TmpSocketMode) == runtime.SocketMode,
        "service_binds_declared_socket":    !state.SocketUnitPresent || (state.ServiceSockets == "collector.socket" && state.ServiceSocketMode == "systemd"),
        "legacy_yaml_fallback_allowed":     !state.SocketUnitPresent && runtime.Authority == "collector.yaml" || state.SocketUnitPresent,
        "lifecycle_socket_inode_stable":    stable,
    }
    if state.SocketUnitPresent {
        checks["main_systemd_socket_authority"] = runtime.Authority == "systemd" && runtime.SocketPath == ExpectedSocketPath
        checks["main_socket_mode_expected"] = runtime.SocketMode == ExpectedMode
        checks["tmpfiles_directory_owned"] = state.TmpDirOwner == ExpectedOwner && state.TmpDirGroup == ExpectedOwner
    } else {
        checks["legacy_fallback_path_present"] = runtime.Authority == "collector.yaml" && runtime.SocketPath == state.ConfigBindPath && runtime.SocketPath != ""
        checks["legacy_service_not_socket_bound"] = state.ServiceSocketMode == "config"
    }

    ok := true
    for _, value := range checks {
        ok = ok && value
    }
    report := Report{
        OK: ok,
        Root: state.Root,
        Runtime: runtime,
        Manifest: ManifestView{Path: manifestPath, Values: manifest, Consistent: consistent, Provenance: manifest["provenance"]},
        Lifecycle: phases,
        Checks: checks,
        Notes: reportNotes(state, runtime, manifest, checks),
    }
    report.Digest = digestReport(report)
    if reportPath != "" {
        if err := writeJSON(reportPath, report); err != nil {
            return Report{}, err
        }
    }
    if tracePath != "" {
        trace := Trace{
            Root: state.Root,
            RuntimeSocket: runtime,
            AuthorityTrace: []AuthorityTrace{
                {Source: "collector.socket", Authority: boolAuthority(state.SocketUnitPresent, "systemd", "absent"), Path: state.ListenStream, Owner: state.SocketUser, Mode: state.SocketMode},
                {Source: "collector.service", Authority: state.ServiceSocketMode, Path: runtime.SocketPath, Owner: runtime.SocketOwner, Mode: runtime.SocketMode},
                {Source: "collector.yaml", Authority: "fallback", Path: state.ConfigBindPath, Owner: state.ConfigSinkOwner, Mode: state.TmpSocketMode},
                {Source: "tmpfiles.d", Authority: "ownership", Path: runtime.SocketPath, Owner: state.TmpSocketOwner, Mode: state.TmpSocketMode},
                {Source: "runtime", Authority: runtime.Authority, Path: runtime.SocketPath, Owner: runtime.SocketOwner, Mode: runtime.SocketMode},
            },
            Phases: phases,
            StableInode: stable,
        }
        if err := writeJSON(tracePath, trace); err != nil {
            return Report{}, err
        }
    }
    return report, nil
}

func lifecycle(runtime RuntimeView) []LifecyclePhase {
    phases := []string{"daemon-reload", "first-activation", "service-restart", "sink-rotation", "report-regeneration"}
    inode := stableInode(runtime.SocketPath, runtime.SocketOwner, runtime.SocketGroup, runtime.SocketMode)
    out := make([]LifecyclePhase, 0, len(phases))
    for _, phase := range phases {
        out = append(out, LifecyclePhase{
            Phase: phase, Authority: runtime.Authority, SocketPath: runtime.SocketPath,
            SocketOwner: runtime.SocketOwner, SocketGroup: runtime.SocketGroup,
            SocketMode: runtime.SocketMode, SocketInode: inode,
        })
    }
    return out
}

func sameInode(phases []LifecyclePhase) bool {
    if len(phases) == 0 {
        return false
    }
    first := phases[0].SocketInode
    for _, phase := range phases[1:] {
        if phase.SocketInode != first {
            return false
        }
    }
    return true
}

func stableInode(parts ...string) string {
    joined := strings.Join(parts, "|")
    sum := sha256.Sum256([]byte(joined))
    return "inode:" + hex.EncodeToString(sum[:])[:16]
}

func reportNotes(state State, runtime RuntimeView, manifest map[string]string, checks map[string]bool) []string {
    notes := []string{}
    if state.SocketUnitPresent {
        notes = append(notes, "socket unit is present, so systemd must be runtime authority")
    } else {
        notes = append(notes, "socket unit is absent, so collector.yaml fallback is accepted")
    }
    if runtime.Authority != manifest["authority"] {
        notes = append(notes, fmt.Sprintf("runtime authority %s differs from manifest authority %s", runtime.Authority, manifest["authority"]))
    }
    keys := make([]string, 0, len(checks))
    for key := range checks {
        keys = append(keys, key)
    }
    sort.Strings(keys)
    for _, key := range keys {
        if !checks[key] {
            notes = append(notes, "unsatisfied: "+key)
        }
    }
    return notes
}

func digestReport(report Report) string {
    clone := report
    clone.Digest = ""
    raw, _ := json.Marshal(clone)
    sum := sha256.Sum256(raw)
    return hex.EncodeToString(sum[:])
}

func writeJSON(path string, value any) error {
    if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
        return err
    }
    raw, err := json.MarshalIndent(value, "", "  ")
    if err != nil {
        return err
    }
    raw = append(raw, '\n')
    return os.WriteFile(path, raw, 0o644)
}

func boolAuthority(ok bool, yes, no string) string {
    if ok {
        return yes
    }
    return no
}

func mapsEqual(a, b map[string]string) bool {
    if len(a) != len(b) {
        return false
    }
    for key, value := range a {
        if b[key] != value {
            return false
        }
    }
    return true
}
