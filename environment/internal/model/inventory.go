package model

type Inventory struct {
	Nodes []Node `json:"nodes"`
}

type Node struct {
	ID       string   `json:"id"`
	Zone     string   `json:"zone"`
	Rack     string   `json:"rack"`
	Power    int      `json:"power"`
	Services []string `json:"services"`
}
