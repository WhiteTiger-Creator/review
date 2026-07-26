package data

import (
	"encoding/csv"
	"os"
	"strconv"
)

type Catalog struct {
	Users   []int
	Items   []int
	UserObs map[int][]Obs
	ItemObs map[int][]Obs
	UserIdx map[int]int
	ItemIdx map[int]int
	RStar   int
	NPairs  int
	Pairs   map[[2]int]int
}

type Obs struct {
	Index int
	Count int
}

// LoadInteractions keeps every ID and does not remass.
func LoadInteractions(path string) (*Catalog, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	r := csv.NewReader(f)
	rows, err := r.ReadAll()
	if err != nil {
		return nil, err
	}
	agg := map[[2]int]int{}
	for _, row := range rows[1:] {
		u, _ := strconv.Atoi(row[0])
		i, _ := strconv.Atoi(row[1])
		c, _ := strconv.Atoi(row[2])
		key := [2]int{u, i}
		agg[key] += c
	}
	cat := FromPairs(agg)
	cat.RStar = 1
	return cat, nil
}

func Remass(pairs map[[2]int]int) map[[2]int]int {
	// lab: identity
	out := map[[2]int]int{}
	for k, v := range pairs {
		out[k] = v
	}
	return out
}

func FromPairs(agg map[[2]int]int) *Catalog {
	userSet := map[int]bool{}
	itemSet := map[int]bool{}
	rStar := 1
	for k, c := range agg {
		userSet[k[0]] = true
		itemSet[k[1]] = true
		if c > rStar {
			rStar = c
		}
	}
	users := sortedKeys(userSet)
	items := sortedKeys(itemSet)
	uIdx := map[int]int{}
	iIdx := map[int]int{}
	for idx, u := range users {
		uIdx[u] = idx
	}
	for idx, i := range items {
		iIdx[i] = idx
	}
	userObs := map[int][]Obs{}
	itemObs := map[int][]Obs{}
	for k, c := range agg {
		ui := uIdx[k[0]]
		ii := iIdx[k[1]]
		userObs[ui] = append(userObs[ui], Obs{Index: ii, Count: c})
		itemObs[ii] = append(itemObs[ii], Obs{Index: ui, Count: c})
	}
	pairsCopy := map[[2]int]int{}
	for k, v := range agg {
		pairsCopy[k] = v
	}
	return &Catalog{
		Users: users, Items: items,
		UserObs: userObs, ItemObs: itemObs,
		UserIdx: uIdx, ItemIdx: iIdx,
		RStar: rStar, NPairs: len(agg), Pairs: pairsCopy,
	}
}

func LoadPairs(path string) ([][2]int, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	r := csv.NewReader(f)
	rows, err := r.ReadAll()
	if err != nil {
		return nil, err
	}
	out := make([][2]int, 0, len(rows))
	for _, row := range rows[1:] {
		u, _ := strconv.Atoi(row[0])
		i, _ := strconv.Atoi(row[1])
		out = append(out, [2]int{u, i})
	}
	return out, nil
}

type HoldRow struct {
	User, Item, Label int
}

func LoadHoldout(path string) ([]HoldRow, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	r := csv.NewReader(f)
	rows, err := r.ReadAll()
	if err != nil {
		return nil, err
	}
	out := make([]HoldRow, 0, len(rows))
	for _, row := range rows[1:] {
		u, _ := strconv.Atoi(row[0])
		i, _ := strconv.Atoi(row[1])
		l, _ := strconv.Atoi(row[2])
		out = append(out, HoldRow{User: u, Item: i, Label: l})
	}
	return out, nil
}

func sortedKeys(m map[int]bool) []int {
	keys := make([]int, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	for i := 0; i < len(keys); i++ {
		for j := i + 1; j < len(keys); j++ {
			if keys[j] < keys[i] {
				keys[i], keys[j] = keys[j], keys[i]
			}
		}
	}
	return keys
}
