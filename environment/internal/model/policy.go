package model

type RollingLimit struct {
	Window         int `json:"window"`
	MaxUnavailable int `json:"max_unavailable"`
}

type Separation struct {
	Left  string `json:"left"`
	Right string `json:"right"`
	Gap   int    `json:"gap"`
}

type Policy struct {
	Targets        []string                `json:"targets"`
	MinAvailable   map[string]int          `json:"min_available"`
	ZoneParallel   map[string]int          `json:"zone_parallel"`
	RackPowerLimit map[string]int          `json:"rack_power_limit"`
	Cooldown       map[string]int          `json:"cooldown"`
	Precedence     [][]string              `json:"precedence"`
	Cohorts        [][]string              `json:"cohorts"`
	Separation     []Separation            `json:"separation"`
	RollingLimits  map[string]RollingLimit `json:"rolling_limits"`
	RiskWeights    map[string]int          `json:"risk_weights"`
	MaxWaveSize    int                     `json:"max_wave_size"`
}
