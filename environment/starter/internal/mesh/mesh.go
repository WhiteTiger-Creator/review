package mesh

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

type LogRecord struct {
	Seq      int      `json:"seq"`
	Ts       string   `json:"ts"`
	UnitID string   `json:"device_id"`
	Op       string   `json:"op"`
	Metric   string   `json:"metric,omitempty"`
	Val      *float64 `json:"val,omitempty"`
	Offset   *float64 `json:"offset,omitempty"`
	Sig      string   `json:"sig"`
}

type Topology struct {
	BoundNodes    []BoundPair     `json:"bound_nodes"`
	HomeSites    map[string][]string `json:"home_sites"`
	SyncMetrics []string            `json:"sync_metrics"`
}

type BoundPair struct {
	Left  string `json:"left"`
	Right string `json:"right"`
}

type MetricStats struct {
	Metric  string  `json:"metric"`
	Min     float64 `json:"min"`
	Max     float64 `json:"max"`
	Average float64 `json:"average"`
	Count   int     `json:"count"`
	Sum     float64 `json:"-"`
}

type UnitState struct {
	UnitID string        `json:"device_id"`
	Active   bool          `json:"active"`
	Metrics  []MetricStats `json:"metrics"`
}

type GatewayState struct {
	GatewayID        string        `json:"gateway_id"`
	Recoverable      bool          `json:"recoverable"`
	ProcessedRecords int           `json:"processed_records"`
	Units            []UnitState `json:"units"`
}

type DriftEvent struct {
	GatewayID string `json:"gateway_id"`
	Seq       int    `json:"seq"`
	UnitID  string `json:"device_id"`
	Reason    string `json:"reason"`
	Detail    string `json:"detail"`
}

type PostureReport struct {
	Recoverable bool           `json:"recoverable"`
	Gateways    []GatewayState `json:"gateways"`
	DriftEvents  []DriftEvent    `json:"drift_events"`
}

type unitProcessState struct {
	unitID    string
	discovered  bool
	retired     bool
	lastSeen    time.Time
	calibOffset float64
	metricStats map[string]*MetricStats
}

func RunReconcile(dataRoot string, topologyPath string) (*PostureReport, error) {
	var topo Topology
	topoData, err := os.ReadFile(topologyPath)
	if err == nil {
		json.Unmarshal(topoData, &topo)
	}

	dataRoot = filepath.Clean(dataRoot)
	entries, err := os.ReadDir(dataRoot)
	if err != nil {
		return &PostureReport{
			Recoverable: false,
		}, nil
	}

	var gatewayDirs []string
	for _, entry := range entries {
		if entry.IsDir() {
			gatewayDirs = append(gatewayDirs, entry.Name())
		}
	}
	sort.Strings(gatewayDirs)

	var gatewaysList []GatewayState
	var driftList []DriftEvent
	globalRecoverable := true

	replicatedStats := make(map[string]map[string]float64)
	for _, m := range topo.SyncMetrics {
		replicatedStats[m] = make(map[string]float64)
	}

	for _, gwID := range gatewayDirs {
		gwDir := filepath.Join(dataRoot, gwID)
		files, err := os.ReadDir(gwDir)
		if err != nil {
			gatewaysList = append(gatewaysList, GatewayState{
				GatewayID:        gwID,
				Recoverable:      false,
				ProcessedRecords: 0,
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

		recordGwDriftEvent := func(seq int, device string, reason, detail string) {
			driftList = append(driftList, DriftEvent{
				GatewayID: gwID,
				Seq:       seq,
				UnitID:  device,
				Reason:    reason,
				Detail:    detail,
			})
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

				vfound := false
				var violationReason, violationDetail string

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
						"BOOT": true, "TELEMETRY": true, "TUNE": true,
						"PING": true, "SHUTDOWN": true, "BATCH_BEGIN": true,
						"BATCH_COMMIT": true, "BATCH_ABORT": true,
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
						valStr = fmt.Sprintf("%f", *rec.Val)
					}
					offStr := ""
					if rec.Offset != nil {
						offStr = fmt.Sprintf("%f", *rec.Offset)
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
						violationDetail = fmt.Sprintf("cannot calibrate undiscovered device: %s", rec.UnitID)
						vfound = true
					}
				}

				if vfound {
					recordGwDriftEvent(rec.Seq, rec.UnitID, violationReason, violationDetail)
					if violationReason == "invalid_seq" || violationReason == "duplicate_seq" || violationReason == "bad_signature" {
						recoverable = false
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
					batchOpen = false
					continue
				} else if rec.Op == "BATCH_ABORT" {
					batchOpen = false
					continue
				}

				uState, hasDevice := unitsMap[rec.UnitID]
				if !hasDevice {
					uState = &unitProcessState{
						unitID:    rec.UnitID,
						metricStats: make(map[string]*MetricStats),
					}
					unitsMap[rec.UnitID] = uState
				}

				if rec.Op == "BOOT" {
					uState.discovered = true
					uState.retired = false
				} else {
					if !uState.discovered {
						recordGwDriftEvent(rec.Seq, rec.UnitID, "orphan_unit", fmt.Sprintf("orphan device event: %s", rec.UnitID))
						continue
					}
					if uState.retired {
						recordGwDriftEvent(rec.Seq, rec.UnitID, "stale_unit_op", fmt.Sprintf("event on retired device: %s", rec.UnitID))
						continue
					}

					if rec.Op == "SHUTDOWN" {
						uState.retired = true
					} else if rec.Op == "TUNE" {
						val := 0.0
						if rec.Offset != nil {
							val = *rec.Offset
						}
						uState.calibOffset = val
					} else if rec.Op == "TELEMETRY" {
						val := 0.0
						if rec.Val != nil {
							val = *rec.Val
						}

						stats, ok := uState.metricStats[rec.Metric]
						calibVal := val - uState.calibOffset
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

		var unitsOut []UnitState
		if recoverable {
			var sortedDevNames []string
			for k := range unitsMap {
				sortedDevNames = append(sortedDevNames, k)
			}
			sort.Strings(sortedDevNames)

			for _, name := range sortedDevNames {
				ds := unitsMap[name]
				if !ds.discovered {
					continue
				}

				var mStatsList []MetricStats
				var sortedMetrics []string
				for mName := range ds.metricStats {
					sortedMetrics = append(sortedMetrics, mName)
				}
				sort.Strings(sortedMetrics)

				for _, mName := range sortedMetrics {
					mStatsList = append(mStatsList, *ds.metricStats[mName])
				}

				unitsOut = append(unitsOut, UnitState{
					UnitID: ds.unitID,
					Active:   !ds.retired,
					Metrics:  mStatsList,
				})

				for _, ms := range mStatsList {
					if rMap, exists := replicatedStats[ms.Metric]; exists {
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
				leftFound := false
				rightFound := false
				for _, d := range gw.Units {
					if d.UnitID == pair.Left {
						leftFound = true
					}
					if d.UnitID == pair.Right {
						rightFound = true
					}
				}
				if leftFound && rightFound {
				}
			}
		}

		for name, allowedGws := range topo.HomeSites {
			for _, gw := range gatewaysList {
				deviceDiscovered := false
				for _, d := range gw.Units {
					if d.UnitID == name {
						deviceDiscovered = true
						break
					}
				}

				if deviceDiscovered {
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
							UnitID:  name,
							Reason:    "site_forbidden",
							Detail:    fmt.Sprintf("unit %s seen on foreign site %s", name, gw.GatewayID),
						})
					}
				}
			}
		}

		for _, mName := range topo.SyncMetrics {
			gwsMap := replicatedStats[mName]
			if len(gwsMap) < 2 {
				continue
			}
			var values []float64
			for _, avg := range gwsMap {
				values = append(values, avg)
			}
			if len(values) >= 2 && math.Abs(values[0]-values[1]) > 0.01 {
				driftList = append(driftList, DriftEvent{
					GatewayID: "",
					Seq:       0,
					UnitID:  "",
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

func WritePosture(report *PostureReport, outputPath string) error {
	dir := filepath.Dir(outputPath)
	os.MkdirAll(dir, 0755)

	f, err := os.Create(outputPath)
	if err != nil {
		return err
	}
	defer f.Close()

	encoder := json.NewEncoder(f)
	encoder.SetIndent("", "  ")
	return encoder.Encode(report)
}

func ReadTopology(path string) (*Topology, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var topo Topology
	json.Unmarshal(data, &topo)
	return &topo, nil
}
