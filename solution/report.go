package planner

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sort"
	"strings"

	"racklight/drainwave/internal/contract"
	"racklight/drainwave/internal/model"
)

func Report(inventory model.Inventory, policy model.Policy, waves [][]string) model.Report {
	nodes := map[string]model.Node{}
	for _, node := range inventory.Nodes {
		nodes[node.ID] = node
	}
	reports := make([]model.WaveReport, 0, len(waves))
	cooldown := map[string]int{}
	for service := range policy.Cooldown {
		cooldown[service] = 0
	}
	recentUnavailable := make([]map[string]int, 0, 3)
	scheduleRisk := 0
	for index, ids := range waves {
		allUnavailable := map[string]int{}
		unavailable := map[string]int{}
		for service := range policy.MinAvailable {
			unavailable[service] = 0
		}
		zones := map[string]int{}
		racks := map[string]int{}
		for _, id := range ids {
			node := nodes[id]
			zones[node.Zone]++
			racks[node.Rack] += node.Power
			for _, service := range node.Services {
				allUnavailable[service]++
				if _, tracked := unavailable[service]; tracked {
					unavailable[service]++
				}
			}
		}
		for service, value := range cooldown {
			if value > 0 {
				cooldown[service] = value - 1
			}
		}
		for service := range allUnavailable {
			if value, tracked := policy.Cooldown[service]; tracked && value > cooldown[service] {
				cooldown[service] = value
			}
		}
		cooldownAfter := map[string]int{}
		for service, value := range cooldown {
			cooldownAfter[service] = value
		}
		rolling := map[string]int{}
		for service, limit := range policy.RollingLimits {
			count := allUnavailable[service]
			for previous := 0; previous < limit.Window-1 && previous < len(recentUnavailable); previous++ {
				count += recentUnavailable[previous][service]
			}
			rolling[service] = count
		}
		waveRisk := 0
		for service, weight := range policy.RiskWeights {
			count := allUnavailable[service]
			waveRisk += weight * count * count
		}
		scheduleRisk += waveRisk
		reports = append(reports, model.WaveReport{
			Wave: index + 1, Nodes: ids, UnavailableServices: unavailable,
			ZoneCounts: zones, RackPower: racks, CooldownAfter: cooldownAfter,
			RollingUnavailable: rolling, WaveRisk: waveRisk,
		})
		recentUnavailable = append([]map[string]int{allUnavailable}, recentUnavailable...)
		if len(recentUnavailable) > 3 {
			recentUnavailable = recentUnavailable[:3]
		}
	}
	return model.Report{Status: contract.StatusOK, WaveCount: len(reports), ScheduleRisk: &scheduleRisk, PlanDigest: digestReports(reports), Waves: reports}
}

func digestReports(reports []model.WaveReport) string {
	var builder strings.Builder
	for _, report := range reports {
		fmt.Fprintf(&builder, "%d|%s|%s|%s|%s|%s|%s|%d\n",
			report.Wave,
			strings.Join(report.Nodes, ","),
			formatMap(report.UnavailableServices),
			formatMap(report.ZoneCounts),
			formatMap(report.RackPower),
			formatMap(report.CooldownAfter),
			formatMap(report.RollingUnavailable),
			report.WaveRisk,
		)
	}
	sum := sha256.Sum256([]byte(builder.String()))
	return "sha256:" + hex.EncodeToString(sum[:])
}

func formatMap(values map[string]int) string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	parts := make([]string, 0, len(keys))
	for _, key := range keys {
		parts = append(parts, fmt.Sprintf("%s=%d", key, values[key]))
	}
	return strings.Join(parts, ",")
}
