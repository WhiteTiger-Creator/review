package types

type FieldCaps struct {
	Fields        int
	SparseSlots   int
	DeclaredScale float32
}

type RouteRow struct {
	ID       string    `json:"id"`
	Features []float32 `json:"features"`
	Observed float32   `json:"observed"`
}

type InferSettings struct {
	ScaleMode   string  `json:"scale_mode"`
	GraphWeight float32 `json:"graph_weight"`
	LaneWeight  float32 `json:"lane_weight"`
}

type RunRec struct {
	InstanceID string  `json:"instance_id"`
	Family     string  `json:"family"`
	Seed       uint64  `json:"seed"`
	Score      float32 `json:"score"`
	Observed   float32 `json:"observed"`
	Delta      float32 `json:"delta"`
	Profile    string  `json:"profile"`
	Generation uint64  `json:"generation"`
}

type OutDoc struct {
	Version int      `json:"version"`
	Runs    []RunRec `json:"runs"`
	Summary struct {
		InstanceCount int      `json:"instance_count"`
		Families      []string `json:"families"`
		Generation    uint64   `json:"generation"`
		ModelID       string   `json:"model_id"`
	} `json:"summary"`
}

type RegistryState struct {
	ModelID       string                    `json:"model_id"`
	ActiveGen     uint64                    `json:"active_generation"`
	Settings      InferSettings             `json:"settings"`
	Lineage       []uint64                  `json:"lineage"`
	EpochToken    string                    `json:"epoch_token"`
	SettingsByGen map[string]InferSettings  `json:"settings_by_gen"`
}

type StagedState struct {
	Generation uint64        `json:"generation"`
	Settings   InferSettings `json:"settings"`
	Incomplete bool          `json:"incomplete"`
	ParentGen  uint64        `json:"parent_generation"`
}

type LedgerEntry struct {
	Key        string `json:"key"`
	Generation uint64 `json:"generation"`
	Fixture    string `json:"fixture"`
	Family     string `json:"family"`
	Seed       uint64 `json:"seed"`
	OutPath    string `json:"out_path"`
	EpochToken string `json:"epoch_token"`
}
