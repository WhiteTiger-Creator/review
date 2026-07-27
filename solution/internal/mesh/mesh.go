package mesh

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"
)

// LogRecord represents a single event record in a gateway JSONL stream.
type LogRecord struct {
	Seq      int      `json:"seq"`
	Ts       string   `json:"ts"`
	UnitID   string   `json:"unit_id"`
	Op       string   `json:"op"`
	Metric   string   `json:"metric,omitempty"`
	Val      *float64 `json:"val,omitempty"`
	Offset   *float64 `json:"offset,omitempty"`
	Sig      string   `json:"sig"`
}

// Topology holds the fleet-wide pairing, authorization, and mirroring rules.
type Topology struct {
	BoundNodes        []BoundPair        `json:"bound_nodes"`
	HomeSites map[string][]string `json:"home_sites"`
	SyncMetrics    []string            `json:"sync_metrics"`
}

// BoundPair is a pair of units that must be co-located.
type BoundPair struct {
	Left  string `json:"left"`
	Right string `json:"right"`
}

// MetricStats tracks streaming telemetry aggregates.
type MetricStats struct {
	Metric  string  `json:"metric"`
	Min     float64 `json:"min"`
	Max     float64 `json:"max"`
	Average float64 `json:"average"`
	Count   int     `json:"count"`
	Sum     float64 `json:"-"`
}

// UnitState is the public state of a unit on a gateway.
type UnitState struct {
	UnitID  string        `json:"unit_id"`
	Active  bool          `json:"active"`
	Metrics []MetricStats `json:"metrics"`
}

// GatewayState is the public state of a gateway.
type GatewayState struct {
	GatewayID        string      `json:"gateway_id"`
	Recoverable      bool        `json:"recoverable"`
	ProcessedRecords int         `json:"processed_records"`
	Units            []UnitState `json:"units"`
}

// DriftEvent represents a processing or topology finding.
type DriftEvent struct {
	GatewayID string `json:"gateway_id"`
	Seq       int    `json:"seq"`
	UnitID    string `json:"unit_id"`
	Reason    string `json:"reason"`
	Detail    string `json:"detail"`
}

// PostureReport is the top-level JSON output.
type PostureReport struct {
	Recoverable bool          `json:"recoverable"`
	Gateways    []GatewayState `json:"gateways"`
	DriftEvents  []DriftEvent   `json:"drift_events"`
}

// Internal unit processing state.
type unitProcessState struct {
	unitID      string
	discovered  bool
	retired     bool
	lastSeen    time.Time
	calibOffset float64
	metricStats map[string]*MetricStats
}

type stagedOp struct {
	op      string
	unitID  string
	metric  string
	val     float64
	offset  float64
}

// RunReconcile processes the gateway data and topology and returns the report.
func RunReconcile(dataRoot string, topologyPath string) (*PostureReport, error) {
	var topo Topology
	topoData, err := os.ReadFile(topologyPath)
	if err == nil {
		if err := json.Unmarshal(topoData, &topo); err != nil {
			return nil, fmt.Errorf("failed to parse topology file: %w", err)
		}
	} else if !os.IsNotExist(err) {
		return nil, fmt.Errorf("failed to read topology file: %w", err)
	}

	if topo.BoundNodes == nil {
		topo.BoundNodes = []BoundPair{}
	}
	if topo.HomeSites == nil {
		topo.HomeSites = make(map[string][]string)
	}
	if topo.SyncMetrics == nil {
		topo.SyncMetrics = []string{}
	}

	dataRoot = filepath.Clean(dataRoot)
	entries, err := os.ReadDir(dataRoot)
	if err != nil {
		return &PostureReport{
			Recoverable: false,
			Gateways:    make([]GatewayState, 0),
			DriftEvents:  make([]DriftEvent, 0),
		}, nil
	}

	var gatewayDirs []string
	for _, entry := range entries {
		if entry.IsDir() {
			gatewayDirs = append(gatewayDirs, entry.Name())
		}
	}
	sort.Strings(gatewayDirs)

	gatewaysList := make([]GatewayState, 0)
	driftList := make([]DriftEvent, 0)
	globalRecoverable := true

	syncStats := make(map[string]map[string]float64)
	for _, m := range topo.SyncMetrics {
		syncStats[m] = make(map[string]float64)
	}

	for _, gwID := range gatewayDirs {
		gwDir := filepath.Join(dataRoot, gwID)
		files, err := os.ReadDir(gwDir)
		if err != nil {
			gatewaysList = append(gatewaysList, GatewayState{
				GatewayID:        gwID,
				Recoverable:      false,
				ProcessedRecords: 0,
				Units:            make([]UnitState, 0),
			})
			globalRecoverable = false
			continue
		}

		var segmentFiles []string
		for _, f := range files {
			if !f.IsDir() && strings.HasPrefix(f.Name(), "seg_") && strings.HasSuffix(f.Name(), ".jsonl") {
				segmentFiles = append(segmentFiles, f.Name())
			}
		}
		sort.Strings(segmentFiles)

		recoverable := true
		processedCount := 0
		expectedSeq := 1
		var lastTime time.Time
		timeInitialized := false

		unitsMap := make(map[string]*unitProcessState)
		batchOpen := false
		stagedOps := make([]stagedOp, 0)

		recordGwDriftEvent := func(seq int, unit string, reason, detail string) {
			driftList = append(driftList, DriftEvent{
				GatewayID: gwID,
				Seq:       seq,
				UnitID:    unit,
				Reason:    reason,
				Detail:    detail,
			})
		}

		commitBatch := func() {
			for _, op := range stagedOps {
				uState, ok := unitsMap[op.unitID]
				if !ok || uState.retired {
					continue
				}
				if op.op == "TELEMETRY" {
					calibVal := op.val + uState.calibOffset
					stats, ok := uState.metricStats[op.metric]
					if !ok {
						stats = &MetricStats{
							Metric:  op.metric,
							Min:     calibVal,
							Max:     calibVal,
							Sum:     calibVal,
							Average: calibVal,
							Count:   1,
						}
						uState.metricStats[op.metric] = stats
					} else {
						stats.Count++
						stats.Sum += calibVal
						if calibVal < stats.Min {
							stats.Min = calibVal
						}
						if calibVal > stats.Max {
							stats.Max = calibVal
						}
						stats.Average = stats.Sum / float64(stats.Count)
					}
				} else if op.op == "TUNE" {
					uState.calibOffset = op.offset
				}
			}
			stagedOps = make([]stagedOp, 0)
			batchOpen = false
		}

		for _, segName := range segmentFiles {
			segPath := filepath.Join(gwDir, segName)
			fileData, readErr := os.ReadFile(segPath)
			if readErr != nil {
				recoverable = false
				break
			}

			lines := strings.Split(string(fileData), "\n")
			for _, line := range lines {
				line = strings.TrimSpace(line)
				if line == "" {
					continue
				}
				processedCount++

				var rec LogRecord
				if errUnmarshal := json.Unmarshal([]byte(line), &rec); errUnmarshal != nil {
					recoverable = false
					recordGwDriftEvent(expectedSeq, "", "bad_signature", "signature hash mismatch")
					continue
				}

				var violationReason, violationDetail string
				vfound := false

				if rec.Seq > 0 && rec.Seq < expectedSeq {
					violationReason = "duplicate_seq"
					violationDetail = fmt.Sprintf("duplicate sequence number: %d", rec.Seq)
					vfound = true
				}

				if !vfound && rec.Seq != expectedSeq {
					violationReason = "invalid_seq"
					violationDetail = fmt.Sprintf("invalid sequence: expected %d, got %d", expectedSeq, rec.Seq)
					vfound = true
				}

				var timestamp time.Time
				if !vfound {
					t, errTs := time.Parse(time.RFC3339, rec.Ts)
					if errTs != nil {
						violationReason = "invalid_timestamp"
						violationDetail = fmt.Sprintf("retrogressive or invalid timestamp: %s", rec.Ts)
						vfound = true
					} else {
						timestamp = t
						if timeInitialized && !timestamp.After(lastTime) && !timestamp.Equal(lastTime) {
							violationReason = "invalid_timestamp"
							violationDetail = fmt.Sprintf("retrogressive or invalid timestamp: %s", rec.Ts)
							vfound = true
						}
					}
				}

				if !vfound {
					validOps := map[string]bool{
						"BOOT": true, "PING": true, "TELEMETRY": true, "TUNE": true,
						"SHUTDOWN": true, "BATCH_BEGIN": true, "BATCH_COMMIT": true, "BATCH_ABORT": true,
					}
					if !validOps[rec.Op] || (rec.Op == "TELEMETRY" && rec.Metric == "") {
						violationReason = "unknown_op_or_metric"
						violationDetail = "unknown op '" + rec.Op + "' or missing metric"
						vfound = true
					}
				}

				if !vfound && rec.UnitID == "" {
					violationReason = "unknown_op_or_metric"
					violationDetail = "unknown op '" + rec.Op + "' or missing metric"
					vfound = true
				}

				if !vfound {
					valStr := ""
					if rec.Val != nil {
						valStr = strconv.FormatFloat(*rec.Val, 'f', 4, 64)
					}
					offStr := ""
					if rec.Offset != nil {
						offStr = strconv.FormatFloat(*rec.Offset, 'f', 4, 64)
					}
					payload := fmt.Sprintf("%s|%d|%s|%s|%s|%s|%s|%s",
						gwID, rec.Seq, rec.Ts, rec.UnitID, rec.Op, rec.Metric, valStr, offStr)
					hash := sha256.Sum256([]byte(payload))
					computedSig := hex.EncodeToString(hash[:])
					if computedSig != rec.Sig {
						violationReason = "bad_signature"
						violationDetail = "signature hash mismatch"
						vfound = true
					}
				}

				if !vfound {
					if rec.Op == "BATCH_COMMIT" || rec.Op == "BATCH_ABORT" {
						if !batchOpen {
							violationReason = "orphan_batch"
							violationDetail = "batch boundary op without open transaction"
							vfound = true
						}
					} else if rec.Op == "BATCH_BEGIN" {
						if batchOpen {
							violationReason = "nested_batch"
							violationDetail = "nested transaction begin not allowed"
							vfound = true
						}
					}
				}

				if !vfound && rec.Op == "TUNE" {
					uState, ok := unitsMap[rec.UnitID]
					if !ok || !uState.discovered {
						violationReason = "tune_missing_unit"
						violationDetail = fmt.Sprintf("cannot tune undiscovered unit: %s", rec.UnitID)
						vfound = true
					}
				}

				if vfound {
					recordGwDriftEvent(rec.Seq, rec.UnitID, violationReason, violationDetail)
					if violationReason == "invalid_seq" || violationReason == "duplicate_seq" || violationReason == "bad_signature" {
						recoverable = false
					}
					if batchOpen {
						stagedOps = make([]stagedOp, 0)
						batchOpen = false
					}
					if violationReason != "invalid_seq" && violationReason != "duplicate_seq" {
						expectedSeq++
					}
					continue
				}

				expectedSeq++
				lastTime = timestamp
				timeInitialized = true

				if rec.Op == "BATCH_BEGIN" {
					batchOpen = true
					continue
				} else if rec.Op == "BATCH_COMMIT" {
					commitBatch()
					continue
				} else if rec.Op == "BATCH_ABORT" {
					stagedOps = make([]stagedOp, 0)
					batchOpen = false
					continue
				}

				uState, hasUnit := unitsMap[rec.UnitID]
				if !hasUnit {
					uState = &unitProcessState{
						unitID:      rec.UnitID,
						metricStats: make(map[string]*MetricStats),
					}
					unitsMap[rec.UnitID] = uState
				}

				if rec.Op == "BOOT" {
					uState.discovered = true
					uState.retired = false
					uState.lastSeen = timestamp
				} else {
					if !uState.discovered {
						recordGwDriftEvent(rec.Seq, rec.UnitID, "orphan_unit", fmt.Sprintf("orphan unit event: %s", rec.UnitID))
						continue
					}
					if uState.retired {
						recordGwDriftEvent(rec.Seq, rec.UnitID, "stale_unit_op", fmt.Sprintf("event on retired unit: %s", rec.UnitID))
						continue
					}
					uState.lastSeen = timestamp

					if rec.Op == "SHUTDOWN" {
						uState.retired = true
					} else if rec.Op == "PING" {
						// lastSeen already updated
					} else if rec.Op == "TUNE" {
						val := 0.0
						if rec.Offset != nil {
							val = *rec.Offset
						}
						if batchOpen {
							stagedOps = append(stagedOps, stagedOp{
								op:      "TUNE",
								unitID:  rec.UnitID,
								offset:  val,
							})
						} else {
							uState.calibOffset = val
						}
					} else if rec.Op == "TELEMETRY" {
						val := 0.0
						if rec.Val != nil {
							val = *rec.Val
						}
						if batchOpen {
							stagedOps = append(stagedOps, stagedOp{
								op:      "TELEMETRY",
								unitID:  rec.UnitID,
								metric:  rec.Metric,
								val:     val,
							})
						} else {
							stats, ok := uState.metricStats[rec.Metric]
							calibVal := val + uState.calibOffset
							if !ok {
								stats = &MetricStats{
									Metric:  rec.Metric,
									Min:     calibVal,
									Max:     calibVal,
									Sum:     calibVal,
									Average: calibVal,
									Count:   1,
								}
								uState.metricStats[rec.Metric] = stats
							} else {
								stats.Count++
								stats.Sum += calibVal
								if calibVal < stats.Min {
									stats.Min = calibVal
								}
								if calibVal > stats.Max {
									stats.Max = calibVal
								}
								stats.Average = stats.Sum / float64(stats.Count)
							}
						}
					}
				}
			}
		}

		if batchOpen {
			stagedOps = make([]stagedOp, 0)
			batchOpen = false
		}

		unitsOut := make([]UnitState, 0)
		if recoverable {
			var sortedUnitNames []string
			for k := range unitsMap {
				sortedUnitNames = append(sortedUnitNames, k)
			}
			sort.Strings(sortedUnitNames)

			for _, name := range sortedUnitNames {
				us := unitsMap[name]
				if !us.discovered {
					continue
				}

				mStatsList := make([]MetricStats, 0)
				var sortedMetrics []string
				for mName := range us.metricStats {
					sortedMetrics = append(sortedMetrics, mName)
				}
				sort.Strings(sortedMetrics)

				for _, mName := range sortedMetrics {
					mStatsList = append(mStatsList, *us.metricStats[mName])
				}

				unitsOut = append(unitsOut, UnitState{
					UnitID:  us.unitID,
					Active:  !us.retired,
					Metrics: mStatsList,
				})

				for _, ms := range mStatsList {
					if rMap, exists := syncStats[ms.Metric]; exists {
						rMap[gwID] = ms.Average
					}
				}
			}
		} else {
			globalRecoverable = false
		}

		gatewaysList = append(gatewaysList, GatewayState{
			GatewayID:        gwID,
			Recoverable:      recoverable,
			ProcessedRecords: processedCount,
			Units:            unitsOut,
		})
	}

	if globalRecoverable {
		for _, pair := range topo.BoundNodes {
			for _, gw := range gatewaysList {
				leftActive := false
				rightActive := false
				for _, u := range gw.Units {
					if u.UnitID == pair.Left && u.Active {
						leftActive = true
					}
					if u.UnitID == pair.Right && u.Active {
						rightActive = true
					}
				}
				if leftActive || rightActive {
					if !leftActive || !rightActive {
						driftList = append(driftList, DriftEvent{
							GatewayID: "",
							Seq:       0,
							UnitID:    "",
							Reason:    "binding_breach",
							Detail:    fmt.Sprintf("binding broken: %s and %s not co-present", pair.Left, pair.Right),
						})
					}
				}
			}
		}

		var homeUnits []string
		for dev := range topo.HomeSites {
			homeUnits = append(homeUnits, dev)
		}
		sort.Strings(homeUnits)
		for _, dev := range homeUnits {
			allowedGws := topo.HomeSites[dev]
			for _, gw := range gatewaysList {
				unitActive := false
				for _, u := range gw.Units {
					if u.UnitID == dev && u.Active {
						unitActive = true
						break
					}
				}
				if unitActive {
					allowed := false
					for _, agw := range allowedGws {
						if agw == gw.GatewayID {
							allowed = true
							break
						}
					}
					if !allowed {
						driftList = append(driftList, DriftEvent{
							GatewayID: "",
							Seq:       0,
							UnitID:    dev,
							Reason:    "site_forbidden",
							Detail:    fmt.Sprintf("unit %s seen on foreign site %s", dev, gw.GatewayID),
						})
					}
				}
			}
		}

		var sortedSyncMetrics []string
		for mName := range syncStats {
			sortedSyncMetrics = append(sortedSyncMetrics, mName)
		}
		sort.Strings(sortedSyncMetrics)

		for _, mName := range sortedSyncMetrics {
			gwsMap := syncStats[mName]
			if len(gwsMap) < 2 {
				continue
			}
			var values []float64
			for _, avg := range gwsMap {
				values = append(values, avg)
			}
			minAvg := values[0]
			maxAvg := values[0]
			for _, val := range values {
				if val < minAvg {
					minAvg = val
				}
				if val > maxAvg {
					maxAvg = val
				}
			}
			if (maxAvg - minAvg) > 0.05 {
				driftList = append(driftList, DriftEvent{
					GatewayID: "",
					Seq:       0,
					UnitID:    "",
					Reason:    "sync_skew",
					Detail:    fmt.Sprintf("sync metric skew: %s exceeds tolerance", mName),
				})
			}
		}
	}

	sort.Slice(driftList, func(i, j int) bool {
		if driftList[i].GatewayID != driftList[j].GatewayID {
			return driftList[i].GatewayID < driftList[j].GatewayID
		}
		return driftList[i].Seq < driftList[j].Seq
	})

	report := &PostureReport{
		Recoverable: globalRecoverable,
		Gateways:    gatewaysList,
		DriftEvents:  driftList,
	}

	return report, nil
}

// WritePosture writes the report to the specified JSON path.
func WritePosture(report *PostureReport, outputPath string) error {
	dir := filepath.Dir(outputPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	f, err := os.Create(outputPath)
	if err != nil {
		return err
	}
	defer f.Close()

	encoder := json.NewEncoder(f)
	encoder.SetIndent("", "  ")
	return encoder.Encode(report)
}

// ReadTopology is a helper to inspect the topology file.
func ReadTopology(path string) (*Topology, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var topo Topology
	if err := json.Unmarshal(data, &topo); err != nil {
		return nil, err
	}
	return &topo, nil
}
