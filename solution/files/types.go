package main

import "encoding/json"

// Hull catalog in normative order.
var hullCatalog = []HullDef{
	{ID: "SCOUT", Atk: 4, Def: 2, FuelCap: 6, BaseRange: 3, Upkeep: 1},
	{ID: "FRIGATE", Atk: 7, Def: 5, FuelCap: 10, BaseRange: 2, Upkeep: 2},
	{ID: "GALLEON", Atk: 11, Def: 8, FuelCap: 14, BaseRange: 2, Upkeep: 3},
	{ID: "FORTRESS", Atk: 9, Def: 14, FuelCap: 12, BaseRange: 1, Upkeep: 4},
}

var hullByID map[string]HullDef

func init() {
	hullByID = map[string]HullDef{}
	for _, h := range hullCatalog {
		hullByID[h.ID] = h
	}
}

type HullDef struct {
	ID        string `json:"id"`
	Atk       int    `json:"atk"`
	Def       int    `json:"def"`
	FuelCap   int    `json:"fuel_cap"`
	BaseRange int    `json:"base_range"`
	Upkeep    int    `json:"upkeep"`
}

type TechDef struct {
	ID              string `json:"id"`
	CostAetherium   int    `json:"cost_aetherium"`
	CostCrystal     int    `json:"cost_crystal"`
	Prerequisite    string `json:"prerequisite"`
	RangeBonus      int    `json:"range_bonus"`
	FuelDiscountPct int    `json:"fuel_discount_pct"`
	AtkPct          int    `json:"atk_pct"`
	DefPct          int    `json:"def_pct"`
	CrownDocks      bool   `json:"crown_docks"`
}

var techCatalog = []TechDef{
	{ID: "LATTICE_SAILS", CostAetherium: 20, CostCrystal: 0, Prerequisite: "", RangeBonus: 1},
	{ID: "AETHER_INJECTORS", CostAetherium: 25, CostCrystal: 10, Prerequisite: "LATTICE_SAILS", FuelDiscountPct: 10},
	{ID: "HARPOON_BALLISTA", CostAetherium: 30, CostCrystal: 15, Prerequisite: "", AtkPct: 10},
	{ID: "SKYIRON_PLATING", CostAetherium: 30, CostCrystal: 15, Prerequisite: "", DefPct: 10},
	{ID: "STORMSEER_LENS", CostAetherium: 40, CostCrystal: 25, Prerequisite: "AETHER_INJECTORS", AtkPct: 5, DefPct: 5},
	{ID: "CROWN_DOCKS", CostAetherium: 50, CostCrystal: 30, Prerequisite: "SKYIRON_PLATING", CrownDocks: true},
}

var techByID map[string]TechDef

func init() {
	techByID = map[string]TechDef{}
	for _, t := range techCatalog {
		techByID[t.ID] = t
	}
}

var weatherMoveMul = map[string]int{
	"CLEAR": 100, "THERMAL": 80, "FOG": 120, "GALE": 150, "STORM": 200,
}

var weatherAtkMul = map[string]int{
	"CLEAR": 100, "THERMAL": 110, "FOG": 85, "GALE": 95, "STORM": 75,
}

var weatherDefMul = map[string]int{
	"CLEAR": 100, "THERMAL": 90, "FOG": 115, "GALE": 95, "STORM": 125,
}

var legalStances = map[string]bool{
	"PEACE": true, "ALLIED": true, "EMBARGO": true, "WAR": true,
}

type Scenario struct {
	ID               string              `json:"id"`
	Name             string              `json:"name"`
	PlayerKingdom    string              `json:"player_kingdom"`
	MaxTurns         int                 `json:"max_turns"`
	Victory          VictorySpec         `json:"victory"`
	Kingdoms         []KingdomSpec       `json:"kingdoms"`
	Islands          []IslandSpec        `json:"islands"`
	Edges            []EdgeSpec          `json:"edges"`
	Fleets           []FleetSpec         `json:"fleets"`
	Captains         []CaptainSpec       `json:"captains"`
	Diplomacy        []DiplomacySpec     `json:"diplomacy"`
	WeatherSchedule  []map[string]string `json:"weather_schedule"`
}

type VictorySpec struct {
	Kind      string `json:"kind"`
	Threshold int    `json:"threshold"`
}

type KingdomSpec struct {
	ID          string   `json:"id"`
	Name        string   `json:"name"`
	Aetherium   int      `json:"aetherium"`
	Crystal     int      `json:"crystal"`
	Timber      int      `json:"timber"`
	Fuel        int      `json:"fuel"`
	Researched  []string `json:"researched"`
}

type IslandSpec struct {
	ID              string `json:"id"`
	Name            string `json:"name"`
	Owner           string `json:"owner"`
	Fortification   int    `json:"fortification"`
	Depot           bool   `json:"depot"`
	Level           int    `json:"level"`
	AetheriumYield  int    `json:"aetherium_yield"`
	CrystalYield    int    `json:"crystal_yield"`
	TimberYield     int    `json:"timber_yield"`
}

type EdgeSpec struct {
	A string `json:"a"`
	B string `json:"b"`
}

type FleetSpec struct {
	ID        string   `json:"id"`
	Kingdom   string   `json:"kingdom"`
	Island    string   `json:"island"`
	Hulls     []string `json:"hulls"`
	Fuel      int      `json:"fuel"`
	Readiness int      `json:"readiness"`
	Captain   string   `json:"captain"`
}

type CaptainSpec struct {
	ID        string `json:"id"`
	Kingdom   string `json:"kingdom"`
	Command   int    `json:"command"`
	Logistics int    `json:"logistics"`
}

type DiplomacySpec struct {
	KingdomA string `json:"kingdom_a"`
	KingdomB string `json:"kingdom_b"`
	Stance   string `json:"stance"`
}

type KingdomState struct {
	ID         string   `json:"id"`
	Name       string   `json:"name"`
	Aetherium  int      `json:"aetherium"`
	Crystal    int      `json:"crystal"`
	Timber     int      `json:"timber"`
	Fuel       int      `json:"fuel"`
	Researched []string `json:"researched"`
}

type IslandState struct {
	ID             string `json:"id"`
	Name           string `json:"name"`
	Owner          string `json:"owner"`
	Fortification  int    `json:"fortification"`
	Depot          bool   `json:"depot"`
	Level          int    `json:"level"`
	AetheriumYield int    `json:"aetherium_yield"`
	CrystalYield   int    `json:"crystal_yield"`
	TimberYield    int    `json:"timber_yield"`
	Weather        string `json:"weather"`
}

type FleetState struct {
	ID        string   `json:"id"`
	Kingdom   string   `json:"kingdom"`
	Island    string   `json:"island"`
	Hulls     []string `json:"hulls"`
	Fuel      int      `json:"fuel"`
	Readiness int      `json:"readiness"`
	Captain   string   `json:"captain"`
}

type CaptainState struct {
	ID        string `json:"id"`
	Kingdom   string `json:"kingdom"`
	Command   int    `json:"command"`
	Logistics int    `json:"logistics"`
}

type ClashResult struct {
	AttackerID         string `json:"attacker_id"`
	DefenderID         string `json:"defender_id"`
	IslandID           string `json:"island_id"`
	AttackerScore      int    `json:"attacker_score"`
	DefenderScore      int    `json:"defender_score"`
	Winner             string `json:"winner"`
	AttackerHullsLost  int    `json:"attacker_hulls_lost"`
	DefenderHullsLost  int    `json:"defender_hulls_lost"`
	OwnershipChanged   bool   `json:"ownership_changed"`
}

type ScoreBreakdown struct {
	Objective  int `json:"objective"`
	Territory  int `json:"territory"`
	Resources  int `json:"resources"`
	Survival   int `json:"survival"`
	Dominance  int `json:"dominance"`
	Violations int `json:"violations"`
	Mission    int `json:"mission"`
	Total      int `json:"total"`
}

type Game struct {
	Scenario       Scenario                 `json:"scenario"`
	State          string                   `json:"state"`
	Turn           int                      `json:"turn"`
	Player         string                   `json:"player"`
	Kingdoms       map[string]*KingdomState `json:"kingdoms"`
	Islands        map[string]*IslandState  `json:"islands"`
	Fleets         map[string]*FleetState   `json:"fleets"`
	Captains       map[string]*CaptainState `json:"captains"`
	Diplomacy      map[string]string        `json:"diplomacy"`
	History        []string                 `json:"history"`
	LastClash      *ClashResult             `json:"last_clash"`
	ScoreBreakdown *ScoreBreakdown          `json:"score_breakdown"`
	graph          map[string][]string      `json:"-"`
}

func cloneJSON[T any](v T) T {
	b, err := json.Marshal(v)
	if err != nil {
		panic(err)
	}
	var out T
	if err := json.Unmarshal(b, &out); err != nil {
		panic(err)
	}
	return out
}

func pairKey(a, b string) string {
	if a < b {
		return a + "|" + b
	}
	return b + "|" + a
}
