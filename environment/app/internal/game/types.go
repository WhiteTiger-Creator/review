package game

type Player struct {
	ID         string `json:"id"`
	Initiative int    `json:"initiative"`
}

type Node struct {
	ID           string  `json:"id"`
	StationID    string  `json:"station_id"`
	BaseDepthM   float64 `json:"base_depth_m"`
	Value        int     `json:"value"`
	InitialOwner string  `json:"owner,omitempty"`
}

type Edge struct {
	A string `json:"a"`
	B string `json:"b"`
}

type Fleet struct {
	ID       string  `json:"id"`
	PlayerID string  `json:"player_id"`
	NodeID   string  `json:"node_id"`
	DraftM   float64 `json:"draft_m"`
}

type Order struct {
	Turn         int    `json:"turn"`
	FleetID      string `json:"fleet_id"`
	Kind         string `json:"kind"`
	TargetNodeID string `json:"target_node_id,omitempty"`
}

type Match struct {
	SchemaVersion int      `json:"schema_version"`
	MatchID       string   `json:"match_id"`
	StartUTC      string   `json:"start_utc"`
	TurnSeconds   int64    `json:"turn_seconds"`
	TurnCount     int      `json:"turn_count"`
	Players       []Player `json:"players"`
	Nodes         []Node   `json:"nodes"`
	Edges         []Edge   `json:"edges"`
	Fleets        []Fleet  `json:"fleets"`
	Orders        []Order  `json:"orders"`
}

type NodeState struct {
	ID              string  `json:"id"`
	TideM           float64 `json:"tide_m"`
	EffectiveDepthM float64 `json:"effective_depth_m"`
	Owner           string  `json:"owner,omitempty"`
}

type FleetState struct {
	ID           string `json:"id"`
	PlayerID     string `json:"player_id"`
	NodeID       string `json:"node_id"`
	Order        string `json:"order"`
	TargetNodeID string `json:"target_node_id,omitempty"`
	Status       string `json:"status"`
}

type Score struct {
	PlayerID string `json:"player_id"`
	Points   int    `json:"points"`
}

type TurnResult struct {
	Turn       int          `json:"turn"`
	UTC        string       `json:"utc"`
	Nodes      []NodeState  `json:"nodes"`
	Fleets     []FleetState `json:"fleets"`
	ScoreDelta []Score      `json:"score_delta"`
	Scores     []Score      `json:"scores"`
}

type FinalNode struct {
	ID    string `json:"id"`
	Owner string `json:"owner,omitempty"`
}

type FinalFleet struct {
	ID       string `json:"id"`
	PlayerID string `json:"player_id"`
	NodeID   string `json:"node_id"`
}

type FinalState struct {
	Winner string       `json:"winner"`
	Scores []Score      `json:"scores"`
	Nodes  []FinalNode  `json:"nodes"`
	Fleets []FinalFleet `json:"fleets"`
}

type Summary struct {
	TurnCount  int    `json:"turn_count"`
	FleetCount int    `json:"fleet_count"`
	SHA256     string `json:"sha256"`
}

type Result struct {
	SchemaVersion int          `json:"schema_version"`
	Game          string       `json:"game"`
	MatchID       string       `json:"match_id"`
	Turns         []TurnResult `json:"turns"`
	Final         FinalState   `json:"final"`
	Summary       Summary      `json:"summary"`
}
