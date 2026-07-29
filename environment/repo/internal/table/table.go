// Package table holds the on-disk shapes of a hand log and a settlement report.
package table

import (
	"encoding/json"
	"fmt"
	"os"
)

// Meld is a called set that is already on the table in front of the player.
type Meld struct {
	// Type is "chi", "pon" or "kan".
	Type string `json:"type"`
	// Tiles is the meld in notation, three tiles for chi and pon, four for kan.
	Tiles string `json:"tiles"`
	// Open is false for a quad declared from a concealed hand.
	Open bool `json:"open"`
}

// Hand is one finished hand from the log.
type Hand struct {
	ID             string   `json:"id"`
	Tiles          string   `json:"hand"`
	Melds          []Meld   `json:"melds"`
	WinTile        string   `json:"winTile"`
	Win            string   `json:"win"`
	SeatWind       string   `json:"seatWind"`
	RoundWind      string   `json:"roundWind"`
	DoraIndicators []string `json:"doraIndicators"`
	Honba          int      `json:"honba"`
	RiichiSticks   int      `json:"riichiSticks"`
	Riichi         bool     `json:"riichi"`
	Ippatsu        bool     `json:"ippatsu"`
	Rinshan        bool     `json:"rinshan"`
	Chankan        bool     `json:"chankan"`
	Haitei         bool     `json:"haitei"`
	Houtei         bool     `json:"houtei"`
	DoubleRiichi   bool     `json:"doubleRiichi"`
	Tenhou         bool     `json:"tenhou"`
	Chiihou        bool     `json:"chiihou"`
}

// SelfDraw reports whether the hand was completed by the winner's own draw.
func (h Hand) SelfDraw() bool { return h.Win == "tsumo" }

// Payment is what the winner collects.
type Payment struct {
	Main            int `json:"main"`
	Additional      int `json:"additional"`
	MainBonus       int `json:"mainBonus"`
	AdditionalBonus int `json:"additionalBonus"`
	RiichiSticks    int `json:"riichiSticks"`
	Total           int `json:"total"`
}

// Result is the settlement of one hand.
type Result struct {
	ID      string   `json:"id"`
	Scored  bool     `json:"scored"`
	Han     int      `json:"han"`
	Fu      int      `json:"fu"`
	Yaku    []string `json:"yaku"`
	Payment *Payment `json:"payment"`
}

// ReadHands loads a hand log.
func ReadHands(path string) ([]Hand, error) {
	blob, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var hands []Hand
	if err := json.Unmarshal(blob, &hands); err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	return hands, nil
}
