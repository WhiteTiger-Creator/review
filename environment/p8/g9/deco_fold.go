package g9

import "encoding/json"

func DecoFold(grid *ScoreGrid) string {
	type row struct {
		ID    uint8  `json:"id"`
		Score uint32 `json:"score"`
	}
	rows := make([]row, len(grid.Scores))
	for i, s := range grid.Scores {
		rows[i] = row{ID: s.ID, Score: s.Score}
	}
	b, _ := json.Marshal(rows)
	return string(b)
}
