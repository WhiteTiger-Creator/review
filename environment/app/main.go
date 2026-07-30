// Command dungeond is the Compose Dungeon game server.
//
// The dungeon map is derived from a Docker Compose file: services are rooms,
// depends_on edges are two-way doors, and dungeon.* labels describe the
// entrance, locks, dark rooms, loot, and the goal room. Every run is saved in
// a bbolt database, together with an append-only journal that powers undo.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"sort"
	"strconv"
	"strings"
	"sync"

	bolt "go.etcd.io/bbolt"
	"gopkg.in/yaml.v3"
)

type room struct {
	Name  string
	Lock  string
	Dark  bool
	Goal  bool
	Items []string
	Exits []string
}

type world struct {
	Entry string
	Rooms map[string]*room
}

// parseWorld reads a Docker Compose file and derives the dungeon map.
// Both label syntaxes (map and "k=v" list) and both depends_on syntaxes
// (short list and long map) are supported.
func parseWorld(path string) (*world, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var doc struct {
		Services map[string]map[string]any `yaml:"services"`
	}
	if err := yaml.Unmarshal(raw, &doc); err != nil {
		return nil, err
	}
	w := &world{Rooms: map[string]*room{}}
	edges := map[string]map[string]bool{}
	addEdge := func(a, b string) {
		if edges[a] == nil {
			edges[a] = map[string]bool{}
		}
		if edges[b] == nil {
			edges[b] = map[string]bool{}
		}
		edges[a][b] = true
		edges[b][a] = true
	}
	for name, svc := range doc.Services {
		r := &room{Name: name, Items: []string{}, Exits: []string{}}
		labels := map[string]string{}
		switch lv := svc["labels"].(type) {
		case map[string]any:
			for k, v := range lv {
				labels[k] = fmt.Sprintf("%v", v)
			}
		case []any:
			for _, entry := range lv {
				parts := strings.SplitN(fmt.Sprintf("%v", entry), "=", 2)
				if len(parts) == 2 {
					labels[parts[0]] = parts[1]
				} else {
					labels[parts[0]] = ""
				}
			}
		}
		if labels["dungeon.entry"] == "true" {
			w.Entry = name
		}
		r.Lock = labels["dungeon.lock"]
		r.Dark = labels["dungeon.dark"] == "true"
		r.Goal = labels["dungeon.goal"] == "true"
		for _, it := range strings.Split(labels["dungeon.items"], ",") {
			if it = strings.TrimSpace(it); it != "" {
				r.Items = append(r.Items, it)
			}
		}
		sort.Strings(r.Items)
		w.Rooms[name] = r
		switch dv := svc["depends_on"].(type) {
		case []any:
			for _, d := range dv {
				addEdge(name, fmt.Sprintf("%v", d))
			}
		case map[string]any:
			for d := range dv {
				addEdge(name, d)
			}
		}
	}
	for name, r := range w.Rooms {
		for other := range edges[name] {
			if _, ok := w.Rooms[other]; ok && other != name {
				r.Exits = append(r.Exits, other)
			}
		}
		sort.Strings(r.Exits)
	}
	return w, nil
}

// loot returns inv plus everything collectible in the given room. Picking up
// is free, and a dark room yields nothing unless a torch is already held.
func (w *world) loot(name string, inv map[string]bool) map[string]bool {
	out := map[string]bool{}
	for k := range inv {
		out[k] = true
	}
	r := w.Rooms[name]
	if r.Dark && !out["torch"] {
		return out
	}
	for _, it := range r.Items {
		out[it] = true
	}
	return out
}

func invKey(inv map[string]bool) string {
	items := make([]string, 0, len(inv))
	for k := range inv {
		items = append(items, k)
	}
	sort.Strings(items)
	return strings.Join(items, "\x00")
}

// reachable computes, as a fixpoint, the set of rooms a fresh run could ever
// enter while greedily looting everything it can along the way.
func (w *world) reachable() map[string]bool {
	reach := map[string]bool{}
	if _, ok := w.Rooms[w.Entry]; !ok {
		return reach
	}
	reach[w.Entry] = true
	inv := map[string]bool{}
	for changed := true; changed; {
		changed = false
		for name := range reach {
			for it := range w.loot(name, inv) {
				if !inv[it] {
					inv[it] = true
					changed = true
				}
			}
		}
		for name, r := range w.Rooms {
			if reach[name] {
				continue
			}
			nextTo := false
			for _, e := range r.Exits {
				if reach[e] {
					nextTo = true
					break
				}
			}
			if !nextTo || (r.Lock != "" && !inv["key."+r.Lock]) {
				continue
			}
			reach[name] = true
			changed = true
		}
	}
	return reach
}

// par returns the fewest successful moves a fresh run needs to stand in the
// goal room, or nil when the dungeon cannot be won. Pickups are free, so the
// search runs over (room, collected loot) states rather than rooms alone:
// detours to fetch a key or a torch cost only the moves they take.
func (w *world) par() *int {
	entry, ok := w.Rooms[w.Entry]
	if !ok {
		return nil
	}
	startInv := w.loot(w.Entry, map[string]bool{})
	if entry.Goal {
		zero := 0
		return &zero
	}
	type state struct {
		room string
		inv  map[string]bool
	}
	queue := []state{{room: w.Entry, inv: startInv}}
	seen := map[string]bool{w.Entry + "|" + invKey(startInv): true}
	for dist := 0; len(queue) > 0; dist++ {
		var next []state
		for _, st := range queue {
			for _, exit := range w.Rooms[st.room].Exits {
				target := w.Rooms[exit]
				if target.Lock != "" && !st.inv["key."+target.Lock] {
					continue
				}
				if target.Goal {
					steps := dist + 1
					return &steps
				}
				inv := w.loot(exit, st.inv)
				key := exit + "|" + invKey(inv)
				if seen[key] {
					continue
				}
				seen[key] = true
				next = append(next, state{room: exit, inv: inv})
			}
		}
		queue = next
	}
	return nil
}

// distToGoal returns the fewest moves needed to enter the goal room starting
// from the given room with the given inventory, looting greedily along the way,
// or -1 when the goal is unreachable from here.
func (w *world) distToGoal(room string, inv map[string]bool) int {
	type state struct {
		room string
		inv  map[string]bool
	}
	start := state{room: room, inv: inv}
	seen := map[string]bool{room + "|" + invKey(inv): true}
	queue := []state{start}
	for dist := 0; len(queue) > 0; dist++ {
		var next []state
		for _, st := range queue {
			for _, exit := range w.Rooms[st.room].Exits {
				target := w.Rooms[exit]
				if target.Lock != "" && !st.inv["key."+target.Lock] {
					continue
				}
				if target.Goal {
					return dist + 1
				}
				ninv := w.loot(exit, st.inv)
				key := exit + "|" + invKey(ninv)
				if seen[key] {
					continue
				}
				seen[key] = true
				next = append(next, state{room: exit, inv: ninv})
			}
		}
		queue = next
	}
	return -1
}

// route returns the lexicographically smallest shortest winning move sequence:
// the list of rooms a fresh player moves into, in order, to first stand in the
// goal room. It is empty when the entry is already the goal, and nil (JSON
// null) when the dungeon cannot be won. At each step it takes the smallest room
// name that keeps the run on a shortest path to the goal, which yields the
// lexicographically smallest sequence among all shortest routes.
func (w *world) route() []string {
	if _, ok := w.Rooms[w.Entry]; !ok {
		return nil
	}
	if w.Rooms[w.Entry].Goal {
		return []string{}
	}
	inv := w.loot(w.Entry, map[string]bool{})
	if w.distToGoal(w.Entry, inv) < 0 {
		return nil
	}
	room := w.Entry
	out := []string{}
	for {
		d := w.distToGoal(room, inv)
		picked := ""
		exits := w.Rooms[room].Exits
		for i := len(exits) - 1; i >= 0; i-- {
			exit := exits[i]
			target := w.Rooms[exit]
			if target.Lock != "" && !inv["key."+target.Lock] {
				continue
			}
			if target.Goal {
				if d == 1 {
					picked = exit
					break
				}
				continue
			}
			if w.distToGoal(exit, w.loot(exit, inv)) == d-1 {
				picked = exit
				break
			}
		}
		if picked == "" {
			return nil
		}
		out = append(out, picked)
		if w.Rooms[picked].Goal {
			return out
		}
		inv = w.loot(picked, inv)
		room = picked
	}
}

// replaySeed is the fixed SplitMix64 seed the demo playthrough starts from.
const replaySeed uint64 = 0x243F6A8885A308D3

// splitmix64 advances the generator state and returns the next 64-bit draw.
func splitmix64(state *uint64) uint64 {
	*state += 0x9E3779B97F4A7C15
	z := *state
	z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9
	z = (z ^ (z >> 28)) * 0x94D049BB133111EB
	z = z ^ (z >> 31)
	return z
}

// boundedRandom returns an unbiased index in [0, n) using rejection sampling:
// draws are skipped when they fall in the incomplete top block, so no modulo
// bias remains. When 2^64 is a multiple of n (n a power of two) nothing is
// skipped.
func boundedRandom(state *uint64, n uint64) uint64 {
	rem := (0 - n) % n // 2^64 mod n
	for {
		v := splitmix64(state)
		if rem == 0 || v < (0-rem) {
			return v % n
		}
	}
}

// replay runs the deterministic demo bot: from the entry it loots greedily and
// steps through a randomly chosen enterable door each turn, for up to 256
// moves or until it reaches the goal.
func (w *world) replay() (uint64, []string, bool) {
	steps := []string{}
	entry, ok := w.Rooms[w.Entry]
	if !ok {
		return replaySeed, steps, false
	}
	inv := w.loot(w.Entry, map[string]bool{})
	if entry.Goal {
		return replaySeed, steps, true
	}
	state := replaySeed
	room := w.Entry
	won := false
	for i := 0; i < 256; i++ {
		var options []string
		for _, exit := range w.Rooms[room].Exits {
			target := w.Rooms[exit]
			if target.Lock != "" && !inv["key."+target.Lock] {
				continue
			}
			options = append(options, exit)
		}
		if len(options) == 0 {
			break
		}
		choice := options[boundedRandom(&state, uint64(len(options)))]
		steps = append(steps, choice)
		room = choice
		inv = w.loot(room, inv)
		if w.Rooms[room].Goal {
			won = true
			break
		}
	}
	return replaySeed, steps, won
}

type session struct {
	ID        string   `json:"id"`
	Room      string   `json:"room"`
	Inventory []string `json:"inventory"`
	Moves     int      `json:"moves"`
	Won       bool     `json:"won"`
}

func (s *session) clone() *session {
	c := *s
	c.Inventory = append([]string{}, s.Inventory...)
	return &c
}

func (s *session) has(item string) bool {
	for _, it := range s.Inventory {
		if it == item {
			return true
		}
	}
	return false
}

var (
	bucketSessions = []byte("sessions")
	bucketJournal  = []byte("journal")
	bucketMeta     = []byte("meta")
	keyLastID      = []byte("last_id")
)

type server struct {
	mu       sync.Mutex
	world    *world
	db       *bolt.DB
	sessions map[string]*session
	history  map[string][]*session
	lastID   uint64
}

func journalKey(id string, seq int) []byte {
	return []byte(fmt.Sprintf("%s:%06d", id, seq))
}

func newServer(w *world, dbPath string) (*server, error) {
	db, err := bolt.Open(dbPath, 0o600, nil)
	if err != nil {
		return nil, err
	}
	s := &server{
		world:    w,
		db:       db,
		sessions: map[string]*session{},
		history:  map[string][]*session{},
	}
	err = db.Update(func(tx *bolt.Tx) error {
		sb, err := tx.CreateBucketIfNotExists(bucketSessions)
		if err != nil {
			return err
		}
		jb, err := tx.CreateBucketIfNotExists(bucketJournal)
		if err != nil {
			return err
		}
		mb, err := tx.CreateBucketIfNotExists(bucketMeta)
		if err != nil {
			return err
		}
		if v := mb.Get(keyLastID); v != nil {
			n, err := strconv.ParseUint(string(v), 10, 64)
			if err != nil {
				return err
			}
			s.lastID = n
		} else if err := mb.Put(keyLastID, []byte("0")); err != nil {
			return err
		}
		if err := sb.ForEach(func(k, v []byte) error {
			var sess session
			if err := json.Unmarshal(v, &sess); err != nil {
				return err
			}
			if sess.Inventory == nil {
				sess.Inventory = []string{}
			}
			s.sessions[string(k)] = &sess
			return nil
		}); err != nil {
			return err
		}
		// Journal keys sort as "<id>:<seq>", so bbolt's byte order already
		// hands back each run's history oldest first.
		return jb.ForEach(func(k, v []byte) error {
			id := string(k)
			if i := strings.LastIndex(id, ":"); i >= 0 {
				id = id[:i]
			}
			var snap session
			if err := json.Unmarshal(v, &snap); err != nil {
				return err
			}
			if snap.Inventory == nil {
				snap.Inventory = []string{}
			}
			s.history[id] = append(s.history[id], &snap)
			return nil
		})
	})
	if err != nil {
		_ = db.Close()
		return nil, err
	}
	return s, nil
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func writeErr(w http.ResponseWriter, status int, code string) {
	writeJSON(w, status, map[string]string{"error": code})
}

// commit writes a state change and its journal effect in one bbolt
// transaction, before any response is written. before is the snapshot to
// append to the journal; when it is nil the newest journal entry is dropped
// instead (undo).
func (s *server) commit(sess *session, before *session, alsoCounter bool) error {
	data, err := json.Marshal(sess)
	if err != nil {
		return err
	}
	var snap []byte
	if before != nil {
		if snap, err = json.Marshal(before); err != nil {
			return err
		}
	}
	return s.db.Update(func(tx *bolt.Tx) error {
		if alsoCounter {
			counter := []byte(strconv.FormatUint(s.lastID, 10))
			if err := tx.Bucket(bucketMeta).Put(keyLastID, counter); err != nil {
				return err
			}
		}
		jb := tx.Bucket(bucketJournal)
		if before != nil {
			seq := len(s.history[sess.ID])
			if err := jb.Put(journalKey(sess.ID, seq), snap); err != nil {
				return err
			}
		} else if n := len(s.history[sess.ID]); n > 0 {
			if err := jb.Delete(journalKey(sess.ID, n)); err != nil {
				return err
			}
		}
		return tx.Bucket(bucketSessions).Put([]byte(sess.ID), data)
	})
}

// apply records the change durably and, only once bbolt has it, updates the
// in-memory run and its undo history.
func (s *server) apply(before, after *session) error {
	if err := s.commit(after, before, false); err != nil {
		return err
	}
	s.history[after.ID] = append(s.history[after.ID], before)
	s.sessions[after.ID] = after
	return nil
}

// decodeField extracts a required non-empty string field from a JSON object
// body; ok is false for malformed bodies.
func decodeField(r *http.Request, field string) (string, bool) {
	var body map[string]any
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		return "", false
	}
	v, ok := body[field].(string)
	if !ok || v == "" {
		return "", false
	}
	return v, true
}

func (s *server) handleCreate(w http.ResponseWriter, _ *http.Request) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.lastID++
	sess := &session{
		ID:        fmt.Sprintf("s%06d", s.lastID),
		Room:      s.world.Entry,
		Inventory: []string{},
	}
	if err := s.commit(sess, nil, true); err != nil {
		s.lastID--
		writeErr(w, http.StatusInternalServerError, "storage")
		return
	}
	s.sessions[sess.ID] = sess
	writeJSON(w, http.StatusCreated, sess)
}

func (s *server) handleGet(w http.ResponseWriter, r *http.Request) {
	s.mu.Lock()
	defer s.mu.Unlock()
	sess, ok := s.sessions[r.PathValue("id")]
	if !ok {
		writeErr(w, http.StatusNotFound, "unknown-session")
		return
	}
	writeJSON(w, http.StatusOK, sess)
}

func (s *server) handleMove(w http.ResponseWriter, r *http.Request) {
	s.mu.Lock()
	defer s.mu.Unlock()
	sess, ok := s.sessions[r.PathValue("id")]
	if !ok {
		writeErr(w, http.StatusNotFound, "unknown-session")
		return
	}
	to, ok := decodeField(r, "to")
	if !ok {
		writeErr(w, http.StatusBadRequest, "bad-request")
		return
	}
	door := false
	for _, e := range s.world.Rooms[sess.Room].Exits {
		if e == to {
			door = true
			break
		}
	}
	if !door {
		writeErr(w, http.StatusConflict, "no-door")
		return
	}
	target, ok := s.world.Rooms[to]
	if !ok {
		writeErr(w, http.StatusConflict, "unknown-room")
		return
	}
	if target.Lock != "" && !sess.has("key."+target.Lock) {
		writeErr(w, http.StatusConflict, "locked")
		return
	}
	if target.Dark && !sess.has("torch") {
		writeErr(w, http.StatusConflict, "dark")
		return
	}
	after := sess.clone()
	after.Room = to
	after.Moves++
	if target.Goal {
		after.Won = true
	}
	if err := s.apply(sess, after); err != nil {
		writeErr(w, http.StatusInternalServerError, "storage")
		return
	}
	writeJSON(w, http.StatusOK, after)
}

func (s *server) handleTake(w http.ResponseWriter, r *http.Request) {
	s.mu.Lock()
	defer s.mu.Unlock()
	sess, ok := s.sessions[r.PathValue("id")]
	if !ok {
		writeErr(w, http.StatusNotFound, "unknown-session")
		return
	}
	item, ok := decodeField(r, "item")
	if !ok {
		writeErr(w, http.StatusBadRequest, "bad-request")
		return
	}
	if sess.has(item) {
		writeJSON(w, http.StatusOK, sess)
		return
	}
	current := s.world.Rooms[sess.Room]
	if current.Dark && !sess.has("torch") {
		writeErr(w, http.StatusConflict, "dark")
		return
	}
	present := false
	for _, it := range current.Items {
		if it == item {
			present = true
			break
		}
	}
	if !present {
		writeErr(w, http.StatusConflict, "no-item")
		return
	}
	after := sess.clone()
	after.Inventory = append(after.Inventory, item)
	sort.Strings(after.Inventory)
	if err := s.apply(sess, after); err != nil {
		writeErr(w, http.StatusInternalServerError, "storage")
		return
	}
	writeJSON(w, http.StatusOK, after)
}

func (s *server) handleUndo(w http.ResponseWriter, r *http.Request) {
	s.mu.Lock()
	defer s.mu.Unlock()
	id := r.PathValue("id")
	if _, ok := s.sessions[id]; !ok {
		writeErr(w, http.StatusNotFound, "unknown-session")
		return
	}
	hist := s.history[id]
	if len(hist) == 0 {
		writeErr(w, http.StatusConflict, "nothing-to-undo")
		return
	}
	restored := hist[len(hist)-1]
	if err := s.commit(restored, nil, false); err != nil {
		writeErr(w, http.StatusInternalServerError, "storage")
		return
	}
	s.history[id] = hist[:len(hist)-1]
	s.sessions[id] = restored
	writeJSON(w, http.StatusOK, restored)
}

type worldRoomJSON struct {
	Name      string   `json:"name"`
	Exits     []string `json:"exits"`
	Lock      *string  `json:"lock"`
	Dark      bool     `json:"dark"`
	Goal      bool     `json:"goal"`
	Items     []string `json:"items"`
	Reachable bool     `json:"reachable"`
}

func (s *server) handleWorld(w http.ResponseWriter, _ *http.Request) {
	s.mu.Lock()
	defer s.mu.Unlock()
	reach := s.world.reachable()
	names := make([]string, 0, len(s.world.Rooms))
	for n := range s.world.Rooms {
		names = append(names, n)
	}
	sort.Strings(names)
	rooms := make([]worldRoomJSON, 0, len(names))
	for _, n := range names {
		rm := s.world.Rooms[n]
		var lock *string
		if rm.Lock != "" {
			l := rm.Lock
			lock = &l
		}
		rooms = append(rooms, worldRoomJSON{
			Name:      n,
			Exits:     rm.Exits,
			Lock:      lock,
			Dark:      rm.Dark,
			Goal:      rm.Goal,
			Items:     rm.Items,
			Reachable: reach[n],
		})
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"entry": s.world.Entry,
		"par":   s.world.par(),
		"route": s.world.route(),
		"rooms": rooms,
	})
}

func (s *server) handleReplay(w http.ResponseWriter, _ *http.Request) {
	s.mu.Lock()
	defer s.mu.Unlock()
	seed, steps, won := s.world.replay()
	writeJSON(w, http.StatusOK, map[string]any{
		"seed":  seed,
		"steps": steps,
		"won":   won,
	})
}

func main() {
	addr := flag.String("addr", "127.0.0.1:8383", "listen address")
	dbPath := flag.String("db", "/app/data/dungeon.db", "bbolt database path")
	composePath := flag.String("compose", "/app/world/docker-compose.yml", "dungeon map (compose file)")
	flag.Parse()

	w, err := parseWorld(*composePath)
	if err != nil {
		log.Fatalf("parse map: %v", err)
	}
	srv, err := newServer(w, *dbPath)
	if err != nil {
		log.Fatalf("open save file: %v", err)
	}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /world", srv.handleWorld)
	mux.HandleFunc("GET /replay", srv.handleReplay)
	mux.HandleFunc("POST /sessions", srv.handleCreate)
	mux.HandleFunc("GET /sessions/{id}", srv.handleGet)
	mux.HandleFunc("POST /sessions/{id}/move", srv.handleMove)
	mux.HandleFunc("POST /sessions/{id}/take", srv.handleTake)
	mux.HandleFunc("POST /sessions/{id}/undo", srv.handleUndo)
	log.Printf("dungeond listening on %s", *addr)
	log.Fatal(http.ListenAndServe(*addr, mux))
}
