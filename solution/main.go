package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
)

type Node struct {
	ID             string `json:"id"`
	Op             string `json:"op"`
	Classification string `json:"classification"`
	OutputBytes    int64  `json:"output_bytes"`
}

type Edge struct {
	ID          string `json:"id"`
	From        string `json:"from"`
	To          string `json:"to"`
	Sensitivity string `json:"sensitivity"`
	TensorBytes int64  `json:"tensor_bytes"`
}

type Graph struct {
	WorkloadID    string     `json:"workload_id"`
	Nodes         []Node     `json:"nodes"`
	Edges         []Edge     `json:"edges"`
	EnclaveGroups [][]string `json:"enclave_groups"`
}

type Mode struct {
	Name           string `json:"name"`
	LatencyUS      int64  `json:"latency_us"`
	WorkspaceBytes int64  `json:"workspace_bytes"`
	ExposurePPM    int64  `json:"exposure_ppm"`
}

type Capability struct {
	Op    string `json:"op"`
	Modes []Mode `json:"modes"`
}

type Provider struct {
	ID           string       `json:"id"`
	MemoryBytes  int64        `json:"memory_bytes"`
	StartupUS    int64        `json:"startup_us"`
	Remote       bool         `json:"remote"`
	TrustLevel   int64        `json:"trust_level"`
	AttestEpoch  int64        `json:"attestation_epoch"`
	KeySlots     int          `json:"key_slots"`
	Capabilities []Capability `json:"capabilities"`
}

type Transfer struct {
	FromProvider string `json:"from_provider"`
	ToProvider   string `json:"to_provider"`
	Encrypted    bool   `json:"encrypted"`
	FixedUS      int64  `json:"fixed_us"`
	PerKiBUS     int64  `json:"per_kib_us"`
	ExposurePPM  int64  `json:"exposure_ppm"`
}

type Conversion struct {
	FromMode    string `json:"from_mode"`
	ToMode      string `json:"to_mode"`
	LatencyUS   int64  `json:"latency_us"`
	ExposurePPM int64  `json:"exposure_ppm"`
}

type ProvidersFile struct {
	Providers   []Provider   `json:"providers"`
	Transfers   []Transfer   `json:"transfers"`
	Conversions []Conversion `json:"conversions"`
}

type PlacementRule struct {
	NodeID             string   `json:"node_id"`
	AllowedProviderIDs []string `json:"allowed_provider_ids"`
	AllowedModes       []string `json:"allowed_modes"`
}

type Policy struct {
	AllowedProviderIDs      []string         `json:"allowed_provider_ids"`
	MinimumTrust            map[string]int64 `json:"minimum_trust"`
	MinimumAttestationEpoch int64            `json:"minimum_attestation_epoch"`
	MaxPathExposurePPM      int64            `json:"max_path_exposure_ppm"`
	MaxRemoteNodes          int              `json:"max_remote_nodes"`
	MaxTransfers            int              `json:"max_transfers"`
	MaxConversions          int              `json:"max_conversions"`
	PlacementRules          []PlacementRule  `json:"placement_rules"`
}

type Candidate struct {
	Provider int
	Mode     Mode
	Key      string
}

type PairKey struct {
	Left  string
	Right string
}

type ChoiceIdentity struct {
	Provider int
	Mode     string
}

type BoundaryOutput struct {
	EdgeID      string `json:"edge_id"`
	Transfer    bool   `json:"transfer"`
	Conversion  bool   `json:"conversion"`
	Encrypted   bool   `json:"encrypted"`
	LatencyUS   int64  `json:"latency_us"`
	ExposurePPM int64  `json:"exposure_ppm"`
}

type PlacementOutput struct {
	NodeID     string `json:"node_id"`
	ProviderID string `json:"provider_id"`
	Mode       string `json:"mode"`
}

type ProviderResourcesOutput struct {
	ProviderID   string `json:"provider_id"`
	UsedBytes    int64  `json:"used_bytes"`
	UsedKeySlots int    `json:"used_key_slots"`
}

type Metrics struct {
	NodeLatencyUS          int64 `json:"node_latency_us"`
	BoundaryLatencyUS      int64 `json:"boundary_latency_us"`
	StartupLatencyUS       int64 `json:"startup_latency_us"`
	TotalLatencyUS         int64 `json:"total_latency_us"`
	PathExposurePPM        int64 `json:"path_exposure_ppm"`
	MaxProviderMemory      int64 `json:"max_provider_memory_bytes"`
	MaxProviderKeySlots    int   `json:"max_provider_key_slots_used"`
	TransferCount          int   `json:"transfer_count"`
	ConversionCount        int   `json:"conversion_count"`
	EncryptedTransferCount int   `json:"encrypted_transfer_count"`
	RemoteNodeCount        int   `json:"remote_node_count"`
}

type Output struct {
	WorkloadID        string                    `json:"workload_id"`
	Status            string                    `json:"status"`
	Placements        []PlacementOutput         `json:"placements"`
	Boundaries        []BoundaryOutput          `json:"boundaries"`
	ProviderResources []ProviderResourcesOutput `json:"provider_resources"`
	Metrics           *Metrics                  `json:"metrics"`
}

type Solver struct {
	graph        Graph
	pf           ProvidersFile
	policy       Policy
	nodeIndex    map[string]int
	incoming     [][]int
	groupOf      []int
	groupChoice  []ChoiceIdentity
	groupSet     []bool
	candidates   [][]Candidate
	transfer     map[PairKey]Transfer
	conversion   map[PairKey]Conversion
	chosen       []Candidate
	assigned     []bool
	pathExposure []int64
	boundaries   []BoundaryOutput
	memory       []int64
	keyUse       []int
	providerUse  []int
	suffixMin    []int64
	suffixMinMem []int64
	best         *Output
	bestSeq      []string
}

func readJSON(path string, dst any) error {
	b, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	if err := json.Unmarshal(b, dst); err != nil {
		return err
	}
	return nil
}

func contains(xs []string, value string) bool {
	for _, x := range xs {
		if x == value {
			return true
		}
	}
	return false
}

func key(a, b string) PairKey { return PairKey{Left: a, Right: b} }

func ceilKiB(byteCount int64) int64 {
	result := byteCount / 1024
	if byteCount%1024 != 0 {
		result++
	}
	return result
}

func newSolver(graph Graph, pf ProvidersFile, policy Policy) (*Solver, error) {
	if graph.WorkloadID == "" || len(graph.Nodes) == 0 || len(pf.Providers) == 0 {
		return nil, errors.New("missing model, nodes, or providers")
	}
	s := &Solver{
		graph: graph, pf: pf, policy: policy,
		nodeIndex: make(map[string]int), transfer: make(map[PairKey]Transfer), conversion: make(map[PairKey]Conversion),
		incoming: make([][]int, len(graph.Nodes)), groupOf: make([]int, len(graph.Nodes)),
		chosen: make([]Candidate, len(graph.Nodes)), assigned: make([]bool, len(graph.Nodes)),
		pathExposure: make([]int64, len(graph.Nodes)), boundaries: make([]BoundaryOutput, len(graph.Edges)),
		memory: make([]int64, len(pf.Providers)), keyUse: make([]int, len(pf.Providers)), providerUse: make([]int, len(pf.Providers)),
	}
	for i := range s.groupOf {
		s.groupOf[i] = -1
	}
	for i, n := range graph.Nodes {
		_, validClass := policy.MinimumTrust[n.Classification]
		if n.ID == "" || n.Op == "" || !validClass || n.OutputBytes <= 0 {
			return nil, errors.New("invalid node")
		}
		if _, exists := s.nodeIndex[n.ID]; exists {
			return nil, errors.New("duplicate node")
		}
		s.nodeIndex[n.ID] = i
	}
	for i, e := range graph.Edges {
		from, ok1 := s.nodeIndex[e.From]
		to, ok2 := s.nodeIndex[e.To]
		_, validSensitivity := policy.MinimumTrust[e.Sensitivity]
		if e.ID == "" || e.TensorBytes <= 0 || !validSensitivity || !ok1 || !ok2 || from >= to {
			return nil, errors.New("invalid edge")
		}
		s.incoming[to] = append(s.incoming[to], i)
	}
	s.groupChoice = make([]ChoiceIdentity, len(graph.EnclaveGroups))
	s.groupSet = make([]bool, len(graph.EnclaveGroups))
	for gi, group := range graph.EnclaveGroups {
		if len(group) < 2 {
			return nil, errors.New("short enclave group")
		}
		for _, id := range group {
			i, ok := s.nodeIndex[id]
			if !ok || s.groupOf[i] != -1 {
				return nil, errors.New("invalid enclave group")
			}
			s.groupOf[i] = gi
		}
	}
	providerIndex := make(map[string]int)
	for i, p := range pf.Providers {
		if p.ID == "" || p.MemoryBytes <= 0 || p.StartupUS < 0 || p.TrustLevel < 0 || p.AttestEpoch < 0 || p.KeySlots < 0 {
			return nil, errors.New("invalid provider")
		}
		if _, exists := providerIndex[p.ID]; exists {
			return nil, errors.New("duplicate provider")
		}
		providerIndex[p.ID] = i
	}
	for _, t := range pf.Transfers {
		s.transfer[key(t.FromProvider, t.ToProvider)] = t
	}
	for _, c := range pf.Conversions {
		s.conversion[key(c.FromMode, c.ToMode)] = c
	}
	rules := make(map[string]PlacementRule)
	for _, rule := range policy.PlacementRules {
		rules[rule.NodeID] = rule
	}
	s.candidates = make([][]Candidate, len(graph.Nodes))
	for ni, n := range graph.Nodes {
		for pi, p := range pf.Providers {
			if !contains(policy.AllowedProviderIDs, p.ID) || p.AttestEpoch < policy.MinimumAttestationEpoch || p.TrustLevel < policy.MinimumTrust[n.Classification] {
				continue
			}
			rule, hasRule := rules[n.ID]
			if hasRule && !contains(rule.AllowedProviderIDs, p.ID) {
				continue
			}
			for _, cap := range p.Capabilities {
				if cap.Op != n.Op {
					continue
				}
				for _, mode := range cap.Modes {
					if hasRule && !contains(rule.AllowedModes, mode.Name) {
						continue
					}
					s.candidates[ni] = append(s.candidates[ni], Candidate{Provider: pi, Mode: mode, Key: p.ID + "/" + mode.Name})
				}
			}
		}
		sort.Slice(s.candidates[ni], func(i, j int) bool { return s.candidates[ni][i].Key < s.candidates[ni][j].Key })
	}
	s.suffixMin = make([]int64, len(graph.Nodes)+1)
	s.suffixMinMem = make([]int64, len(graph.Nodes)+1)
	for i := len(graph.Nodes) - 1; i >= 0; i-- {
		if len(s.candidates[i]) == 0 {
			s.suffixMin[i] = s.suffixMin[i+1]
			s.suffixMinMem[i] = s.suffixMinMem[i+1]
		} else {
			m := s.candidates[i][0].Mode.LatencyUS
			minMemory := graph.Nodes[i].OutputBytes + s.candidates[i][0].Mode.WorkspaceBytes
			for _, c := range s.candidates[i][1:] {
				if c.Mode.LatencyUS < m {
					m = c.Mode.LatencyUS
				}
				candidateMemory := graph.Nodes[i].OutputBytes + c.Mode.WorkspaceBytes
				if candidateMemory < minMemory {
					minMemory = candidateMemory
				}
			}
			s.suffixMin[i] = s.suffixMin[i+1] + m
			s.suffixMinMem[i] = s.suffixMinMem[i+1] + minMemory
		}
	}
	return s, nil
}

func (s *Solver) better(metrics Metrics, seq []string) bool {
	if s.best == nil {
		return true
	}
	b := s.best.Metrics
	aNums := []int64{metrics.TotalLatencyUS, metrics.PathExposurePPM, metrics.MaxProviderMemory, int64(metrics.MaxProviderKeySlots), int64(metrics.TransferCount), int64(metrics.ConversionCount)}
	bNums := []int64{b.TotalLatencyUS, b.PathExposurePPM, b.MaxProviderMemory, int64(b.MaxProviderKeySlots), int64(b.TransferCount), int64(b.ConversionCount)}
	for i := range aNums {
		if aNums[i] != bNums[i] {
			return aNums[i] < bNums[i]
		}
	}
	for i := range seq {
		if seq[i] != s.bestSeq[i] {
			return seq[i] < s.bestSeq[i]
		}
	}
	return false
}

func (s *Solver) lowerBoundCannotBeat(idx int, nodeLatency, boundaryLatency int64, transfers, conversions int) bool {
	if s.best == nil {
		return false
	}
	startup := int64(0)
	for i, count := range s.providerUse {
		if count > 0 {
			startup += s.pf.Providers[i].StartupUS
		}
	}
	maxExposure := int64(0)
	for i := 0; i < idx; i++ {
		if s.pathExposure[i] > maxExposure {
			maxExposure = s.pathExposure[i]
		}
	}
	maxMemory := int64(0)
	maxKeys := 0
	totalMemory := s.suffixMinMem[idx]
	for i := range s.pf.Providers {
		totalMemory += s.memory[i]
		if s.memory[i] > maxMemory {
			maxMemory = s.memory[i]
		}
		if s.keyUse[i] > maxKeys {
			maxKeys = s.keyUse[i]
		}
	}
	averageMemoryLowerBound := totalMemory / int64(len(s.pf.Providers))
	if totalMemory%int64(len(s.pf.Providers)) != 0 {
		averageMemoryLowerBound++
	}
	if averageMemoryLowerBound > maxMemory {
		maxMemory = averageMemoryLowerBound
	}
	lowerNumbers := []int64{
		nodeLatency + boundaryLatency + startup + s.suffixMin[idx],
		maxExposure,
		maxMemory,
		int64(maxKeys),
		int64(transfers),
		int64(conversions),
	}
	best := s.best.Metrics
	bestNumbers := []int64{
		best.TotalLatencyUS,
		best.PathExposurePPM,
		best.MaxProviderMemory,
		int64(best.MaxProviderKeySlots),
		int64(best.TransferCount),
		int64(best.ConversionCount),
	}
	for i := range lowerNumbers {
		if lowerNumbers[i] != bestNumbers[i] {
			return lowerNumbers[i] > bestNumbers[i]
		}
	}
	for i := range s.graph.Nodes {
		choiceKey := ""
		if i < idx {
			choiceKey = s.chosen[i].Key
		} else {
			if len(s.candidates[i]) == 0 {
				return true
			}
			choiceKey = s.candidates[i][0].Key
		}
		if choiceKey != s.bestSeq[i] {
			return choiceKey > s.bestSeq[i]
		}
	}
	return true
}

func (s *Solver) search(idx int, nodeLatency, boundaryLatency int64, transfers, conversions, encrypted, remote int) {
	if transfers > s.policy.MaxTransfers || conversions > s.policy.MaxConversions || remote > s.policy.MaxRemoteNodes {
		return
	}
	if s.lowerBoundCannotBeat(idx, nodeLatency, boundaryLatency, transfers, conversions) {
		return
	}
	if idx == len(s.graph.Nodes) {
		startup, maxMem := int64(0), int64(0)
		maxKeys := 0
		providerResources := make([]ProviderResourcesOutput, len(s.pf.Providers))
		for i, p := range s.pf.Providers {
			if s.providerUse[i] > 0 {
				startup += p.StartupUS
			}
			if s.memory[i] > maxMem {
				maxMem = s.memory[i]
			}
			if s.keyUse[i] > maxKeys {
				maxKeys = s.keyUse[i]
			}
			providerResources[i] = ProviderResourcesOutput{ProviderID: p.ID, UsedBytes: s.memory[i], UsedKeySlots: s.keyUse[i]}
		}
		maxExposure := int64(0)
		for _, value := range s.pathExposure {
			if value > maxExposure {
				maxExposure = value
			}
		}
		metrics := Metrics{NodeLatencyUS: nodeLatency, BoundaryLatencyUS: boundaryLatency, StartupLatencyUS: startup,
			TotalLatencyUS: nodeLatency + boundaryLatency + startup, PathExposurePPM: maxExposure, MaxProviderMemory: maxMem,
			MaxProviderKeySlots: maxKeys, TransferCount: transfers, ConversionCount: conversions,
			EncryptedTransferCount: encrypted, RemoteNodeCount: remote}
		seq := make([]string, len(s.chosen))
		placements := make([]PlacementOutput, len(s.chosen))
		for i, c := range s.chosen {
			seq[i] = c.Key
			placements[i] = PlacementOutput{NodeID: s.graph.Nodes[i].ID, ProviderID: s.pf.Providers[c.Provider].ID, Mode: c.Mode.Name}
		}
		if !s.better(metrics, seq) {
			return
		}
		bounds := make([]BoundaryOutput, len(s.boundaries))
		copy(bounds, s.boundaries)
		s.best = &Output{WorkloadID: s.graph.WorkloadID, Status: "ok", Placements: placements, Boundaries: bounds, ProviderResources: providerResources, Metrics: &metrics}
		s.bestSeq = append([]string(nil), seq...)
		return
	}
	n := s.graph.Nodes[idx]
	for _, cand := range s.candidates[idx] {
		gi := s.groupOf[idx]
		setGroup := false
		if gi >= 0 {
			if s.groupSet[gi] && (s.groupChoice[gi].Provider != cand.Provider || s.groupChoice[gi].Mode != cand.Mode.Name) {
				continue
			}
			if !s.groupSet[gi] {
				s.groupChoice[gi] = ChoiceIdentity{Provider: cand.Provider, Mode: cand.Mode.Name}
				s.groupSet[gi] = true
				setGroup = true
			}
		}
		addedMem := n.OutputBytes + cand.Mode.WorkspaceBytes
		if s.memory[cand.Provider]+addedMem > s.pf.Providers[cand.Provider].MemoryBytes {
			if setGroup {
				s.groupSet[gi] = false
			}
			continue
		}
		pathBase := int64(0)
		edgeLatency := int64(0)
		addT, addC, addEncrypted := 0, 0, 0
		keyAdds := make([]int, len(s.pf.Providers))
		valid := true
		for _, ei := range s.incoming[idx] {
			e := s.graph.Edges[ei]
			pred := s.nodeIndex[e.From]
			pc := s.chosen[pred]
			bo := BoundaryOutput{EdgeID: e.ID}
			if pc.Provider != cand.Provider {
				t, ok := s.transfer[key(s.pf.Providers[pc.Provider].ID, s.pf.Providers[cand.Provider].ID)]
				if !ok {
					valid = false
					break
				}
				bo.Transfer = true
				if e.Sensitivity != "public" && !t.Encrypted {
					valid = false
					break
				}
				bo.Encrypted = t.Encrypted
				bo.LatencyUS += t.FixedUS + ceilKiB(e.TensorBytes)*t.PerKiBUS
				bo.ExposurePPM += t.ExposurePPM
				addT++
				if t.Encrypted {
					keyAdds[pc.Provider]++
					keyAdds[cand.Provider]++
					addEncrypted++
				}
			}
			if pc.Mode.Name != cand.Mode.Name {
				c, ok := s.conversion[key(pc.Mode.Name, cand.Mode.Name)]
				if !ok {
					valid = false
					break
				}
				bo.Conversion = true
				bo.LatencyUS += c.LatencyUS
				bo.ExposurePPM += c.ExposurePPM
				addC++
			}
			s.boundaries[ei] = bo
			edgeLatency += bo.LatencyUS
			v := s.pathExposure[pred] + bo.ExposurePPM
			if v > pathBase {
				pathBase = v
			}
		}
		for providerIndex, added := range keyAdds {
			if s.keyUse[providerIndex]+added > s.pf.Providers[providerIndex].KeySlots {
				valid = false
				break
			}
		}
		path := pathBase + cand.Mode.ExposurePPM
		if !valid || path > s.policy.MaxPathExposurePPM || transfers+addT > s.policy.MaxTransfers || conversions+addC > s.policy.MaxConversions {
			if setGroup {
				s.groupSet[gi] = false
			}
			continue
		}
		s.chosen[idx] = cand
		s.assigned[idx] = true
		s.pathExposure[idx] = path
		s.memory[cand.Provider] += addedMem
		for providerIndex, added := range keyAdds {
			s.keyUse[providerIndex] += added
		}
		s.providerUse[cand.Provider]++
		addRemote := 0
		if s.pf.Providers[cand.Provider].Remote {
			addRemote = 1
		}
		s.search(idx+1, nodeLatency+cand.Mode.LatencyUS, boundaryLatency+edgeLatency, transfers+addT, conversions+addC, encrypted+addEncrypted, remote+addRemote)
		s.providerUse[cand.Provider]--
		for providerIndex, added := range keyAdds {
			s.keyUse[providerIndex] -= added
		}
		s.memory[cand.Provider] -= addedMem
		s.assigned[idx] = false
		if setGroup {
			s.groupSet[gi] = false
		}
	}
}

func solve(bundle string) (Output, error) {
	var graph Graph
	var pf ProvidersFile
	var policy Policy
	if err := readJSON(filepath.Join(bundle, "graph.json"), &graph); err != nil {
		return Output{}, err
	}
	if err := readJSON(filepath.Join(bundle, "providers.json"), &pf); err != nil {
		return Output{}, err
	}
	if err := readJSON(filepath.Join(bundle, "policy.json"), &policy); err != nil {
		return Output{}, err
	}
	s, err := newSolver(graph, pf, policy)
	if err != nil {
		return Output{}, err
	}
	s.search(0, 0, 0, 0, 0, 0, 0)
	if s.best == nil {
		return Output{WorkloadID: graph.WorkloadID, Status: "unsatisfied", Placements: []PlacementOutput{}, Boundaries: []BoundaryOutput{}, ProviderResources: []ProviderResourcesOutput{}, Metrics: nil}, nil
	}
	return *s.best, nil
}

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: partitionplan <bundle-dir> <output.json>")
		os.Exit(2)
	}
	out, err := solve(os.Args[1])
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	b, err := json.MarshalIndent(out, "", "  ")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := os.MkdirAll(filepath.Dir(os.Args[2]), 0755); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := os.WriteFile(os.Args[2], append(b, '\n'), 0644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
