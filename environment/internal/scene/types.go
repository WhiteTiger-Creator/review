package scene

type Solid struct {
	Y     float64 `json:"y"`
	X0    float64 `json:"x0"`
	X1    float64 `json:"x1"`
	OneWay bool   `json:"one_way"`
}

type Case struct {
	ID     string  `json:"id"`
	StartX float64 `json:"start_x"`
	StartY float64 `json:"start_y"`
	VX     float64 `json:"vx"`
	Ticks  int     `json:"ticks"`
	Skin   float64 `json:"skin"`
	Press  []int   `json:"press"`
	Solids []Solid `json:"solids"`
}

type Bundle struct {
	ID    string   `json:"id"`
	Cases []string `json:"cases"`
}
