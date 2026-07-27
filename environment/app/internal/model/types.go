package model

type Overrides struct {
	DatumM         *float64 `json:"datum_m,omitempty"`
	Scale          *float64 `json:"scale,omitempty"`
	PhaseOffsetDeg *float64 `json:"phase_offset_deg,omitempty"`
}

type ConstituentUse struct {
	Name      string  `json:"name"`
	Amplitude float64 `json:"amplitude_m"`
	PhaseDeg  float64 `json:"phase_deg"`
	Required  bool    `json:"required"`
}

type Station struct {
	ID           string           `json:"id"`
	Region       string           `json:"region,omitempty"`
	LatitudeDeg  float64          `json:"latitude_deg"`
	LongitudeDeg float64          `json:"longitude_deg"`
	Overrides    Overrides        `json:"overrides,omitempty"`
	Constituents []ConstituentUse `json:"constituents"`
}

type Bundle struct {
	SchemaVersion int                  `json:"schema_version"`
	Global        Overrides            `json:"global,omitempty"`
	Regions       map[string]Overrides `json:"regions,omitempty"`
	Stations      []Station            `json:"stations"`
}

type NodalNode struct {
	TAI                 int64   `json:"tai"`
	Factor              float64 `json:"factor"`
	FactorSlopePerSec   float64 `json:"factor_slope_per_sec"`
	PhaseDeg            float64 `json:"phase_deg"`
	PhaseSlopeDegPerSec float64 `json:"phase_slope_deg_per_sec"`
}

type CatalogEntry struct {
	SchemaVersion   int         `json:"schema_version"`
	Name            string      `json:"name"`
	SpeedDegPerHour float64     `json:"speed_deg_per_hour"`
	EpochTAI        int64       `json:"epoch_tai"`
	Nodal           []NodalNode `json:"nodal"`
}

type Sample struct {
	UTC     string  `json:"utc"`
	TAI     int64   `json:"tai"`
	HeightM float64 `json:"height_m"`
}

type StationResult struct {
	ID              string   `json:"id"`
	OmittedOptional []string `json:"omitted_optional"`
	Samples         []Sample `json:"samples"`
}

type Summary struct {
	SampleCount int    `json:"sample_count"`
	SHA256      string `json:"sha256"`
}

type Output struct {
	SchemaVersion int             `json:"schema_version"`
	GeneratedBy   string          `json:"generated_by"`
	StartUTC      string          `json:"start_utc"`
	StepSeconds   int64           `json:"step_seconds"`
	Count         int             `json:"count"`
	Stations      []StationResult `json:"stations"`
	Summary       Summary         `json:"summary"`
}
