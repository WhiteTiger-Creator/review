package forecast

import (
	"fmt"
	"math"
	"sort"
	"sync"
	"tidefront.local/game/internal/config"
	"tidefront.local/game/internal/model"
	"tidefront.local/game/internal/timebridge"
)

type Engine struct {
	Bundle  model.Bundle
	Catalog map[string]model.CatalogEntry
	Clock   *timebridge.Table
	Threads int
}

type stationJob struct {
	idx     int
	station model.Station
}
type stationReply struct {
	result model.StationResult
	err    error
}

func ValidateBundle(b model.Bundle) error {
	if b.SchemaVersion != 1 {
		return fmt.Errorf("station bundle schema_version must be 1")
	}
	if len(b.Stations) == 0 {
		return fmt.Errorf("station bundle must contain at least one station")
	}
	stationIDs := map[string]struct{}{}
	for _, s := range b.Stations {
		if s.ID == "" {
			return fmt.Errorf("station id is required")
		}
		if _, ok := stationIDs[s.ID]; ok {
			return fmt.Errorf("duplicate station id %s", s.ID)
		}
		stationIDs[s.ID] = struct{}{}
		if s.LatitudeDeg < -90 || s.LatitudeDeg > 90 || s.LongitudeDeg < -180 || s.LongitudeDeg > 180 {
			return fmt.Errorf("station %s coordinates out of range", s.ID)
		}
		if s.Region != "" {
			if _, ok := b.Regions[s.Region]; !ok {
				return fmt.Errorf("station %s references unknown region %s", s.ID, s.Region)
			}
		}
		if len(s.Constituents) == 0 {
			return fmt.Errorf("station %s must declare constituents", s.ID)
		}
		seen := map[string]struct{}{}
		for _, u := range s.Constituents {
			if u.Name == "" || !isFinite(u.Amplitude) || u.Amplitude < 0 || !isFinite(u.PhaseDeg) {
				return fmt.Errorf("station %s has invalid constituent", s.ID)
			}
			if _, ok := seen[u.Name]; ok {
				return fmt.Errorf("station %s has duplicate constituent %s", s.ID, u.Name)
			}
			seen[u.Name] = struct{}{}
		}
	}
	for name, ov := range b.Regions {
		if name == "" || !validOverrides(ov) {
			return fmt.Errorf("invalid region override %q", name)
		}
	}
	if !validOverrides(b.Global) {
		return fmt.Errorf("invalid global override")
	}
	return nil
}

func validOverrides(o model.Overrides) bool {
	for _, p := range []*float64{o.DatumM, o.Scale, o.PhaseOffsetDeg} {
		if p != nil && !isFinite(*p) {
			return false
		}
	}
	return true
}
func isFinite(v float64) bool { return !math.IsNaN(v) && !math.IsInf(v, 0) }

func (e *Engine) Run(startUTC string, step int64, count int) ([]model.StationResult, error) {
	if err := ValidateBundle(e.Bundle); err != nil {
		return nil, err
	}
	if step <= 0 || count <= 0 || count > 100000 {
		return nil, fmt.Errorf("step_seconds and count must be positive and count must not exceed 100000")
	}
	startTAI, err := e.Clock.UTCToTAI(startUTC)
	if err != nil {
		return nil, fmt.Errorf("start_utc: %w", err)
	}
	threads := e.Threads
	if threads < 1 {
		threads = 1
	}
	if threads > len(e.Bundle.Stations) {
		threads = len(e.Bundle.Stations)
	}
	jobs := make(chan stationJob)
	replies := make(chan stationReply, len(e.Bundle.Stations))
	var wg sync.WaitGroup
	for i := 0; i < threads; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for job := range jobs {
				r, err := e.runStation(job.station, startTAI, step, count)
				replies <- stationReply{r, err}
			}
		}()
	}
	go func() {
		for i, s := range e.Bundle.Stations {
			jobs <- stationJob{i, s}
		}
		close(jobs)
		wg.Wait()
		close(replies)
	}()
	results := make([]model.StationResult, 0, len(e.Bundle.Stations))
	for reply := range replies {
		if reply.err != nil {
			return nil, reply.err
		}
		results = append(results, reply.result)
	}
	sort.Slice(results, func(i, j int) bool { return results[i].ID < results[j].ID })
	return results, nil
}

func (e *Engine) runStation(s model.Station, startTAI, step int64, count int) (model.StationResult, error) {
	eff := config.Resolve(e.Bundle, s)
	uses := append([]model.ConstituentUse(nil), s.Constituents...)
	sort.Slice(uses, func(i, j int) bool { return uses[i].Name < uses[j].Name })
	present := make([]struct {
		use   model.ConstituentUse
		entry model.CatalogEntry
	}, 0, len(uses))
	omitted := []string{}
	for _, u := range uses {
		entry, ok := e.Catalog[u.Name]
		if !ok {
			if u.Required {
				return model.StationResult{}, fmt.Errorf("station %s requires missing constituent %s", s.ID, u.Name)
			}
			omitted = append(omitted, u.Name)
			continue
		}
		present = append(present, struct {
			use   model.ConstituentUse
			entry model.CatalogEntry
		}{u, entry})
	}
	sort.Strings(omitted)
	samples := make([]model.Sample, count)
	for i := 0; i < count; i++ {
		tai := startTAI + int64(i)*step
		utc, err := e.Clock.TAIToUTC(tai)
		if err != nil {
			return model.StationResult{}, fmt.Errorf("sample %d UTC conversion: %w", i, err)
		}
		height := eff.DatumM
		for _, p := range present {
			factor, nphase, err := interpolate(p.entry, tai)
			if err != nil {
				return model.StationResult{}, fmt.Errorf("station %s constituent %s: %w", s.ID, p.use.Name, err)
			}
			angle := p.use.PhaseDeg + eff.PhaseOffsetDeg + nphase + p.entry.SpeedDegPerHour*float64(tai-p.entry.EpochTAI)/3600.0 + s.LongitudeDeg
			height += eff.Scale * p.use.Amplitude * factor * math.Cos(timebridge.Wrap(angle)*math.Pi/180.0)
		}
		height = math.RoundToEven(height*1_000_000) / 1_000_000
		if height == 0 {
			height = 0
		}
		samples[i] = model.Sample{UTC: utc, TAI: tai, HeightM: height}
	}
	return model.StationResult{ID: s.ID, OmittedOptional: omitted, Samples: samples}, nil
}

func interpolate(entry model.CatalogEntry, tai int64) (float64, float64, error) {
	nodes := entry.Nodal
	if tai < nodes[0].TAI || tai > nodes[len(nodes)-1].TAI {
		return 0, 0, fmt.Errorf("sample outside nodal coverage")
	}
	idx := sort.Search(len(nodes), func(i int) bool { return nodes[i].TAI >= tai })
	if idx == 0 {
		return nodes[0].Factor, timebridge.Wrap(nodes[0].PhaseDeg), nil
	}
	if idx == len(nodes) {
		idx = len(nodes) - 1
	}
	if nodes[idx].TAI == tai {
		return nodes[idx].Factor, timebridge.Wrap(nodes[idx].PhaseDeg), nil
	}
	a, b := nodes[idx-1], nodes[idx]
	span := float64(b.TAI - a.TAI)
	t := float64(tai-a.TAI) / span
	factor := timebridge.Hermite(a.Factor, a.FactorSlopePerSec, b.Factor, b.FactorSlopePerSec, t, span)
	if factor < 0 {
		return 0, 0, fmt.Errorf("interpolated nodal factor is negative")
	}
	phase := timebridge.PhaseHermite(a.PhaseDeg, a.PhaseSlopeDegPerSec, b.PhaseDeg, b.PhaseSlopeDegPerSec, t, span)
	return factor, phase, nil
}
