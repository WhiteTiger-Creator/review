package model

type Report struct {
	Status       string       `json:"status"`
	WaveCount    int          `json:"wave_count,omitempty"`
	ScheduleRisk *int         `json:"schedule_risk,omitempty"`
	PlanDigest   string       `json:"plan_digest,omitempty"`
	Waves        []WaveReport `json:"waves,omitempty"`
	Reason       string       `json:"reason,omitempty"`
}

type WaveReport struct {
	Wave                int            `json:"wave"`
	Nodes               []string       `json:"nodes"`
	UnavailableServices map[string]int `json:"unavailable_services"`
	ZoneCounts          map[string]int `json:"zone_counts"`
	RackPower           map[string]int `json:"rack_power"`
	CooldownAfter       map[string]int `json:"cooldown_after"`
	RollingUnavailable  map[string]int `json:"rolling_unavailable"`
	WaveRisk            int            `json:"wave_risk"`
}
