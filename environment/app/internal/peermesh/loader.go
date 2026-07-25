package peermesh

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
)

// Peer is one WireGuard peer inventory record.
type Peer struct {
	PeerID        string `json:"peer_id"`
	MeshID        string `json:"mesh_id"`
	PublicKey     string `json:"public_key"`
	Endpoint      string `json:"endpoint"`
	AllowedIP     string `json:"allowed_ip"`
	Iface         string `json:"iface"`
	KeepaliveSec  int    `json:"keepalive_sec"`
	LastHandshake int64  `json:"last_handshake"`
	State         string `json:"state"`
	Family        int    `json:"family"`
}

// MeshNet is a named mesh AllowedIPs CIDR.
type MeshNet struct {
	MeshID string `json:"mesh_id"`
	CIDR   string `json:"cidr"`
}

// EndpointBind maps an authorized public_key+iface to the expected endpoint.
type EndpointBind struct {
	PublicKey string `json:"public_key"`
	Iface     string `json:"iface"`
	Endpoint  string `json:"endpoint"`
}

// Corpus is the full inventory snapshot.
type Corpus struct {
	Peers     []Peer
	Meshes    []MeshNet
	Endpoints []EndpointBind
}

// Load reads mesh nets, endpoint bindings, and all peer JSON files under inventoryRoot.
func Load(inventoryRoot string) (Corpus, error) {
	var c Corpus

	meshesPath := filepath.Join(inventoryRoot, "meshes", "m01.json")
	mb, err := os.ReadFile(meshesPath)
	if err != nil {
		return c, fmt.Errorf("meshes: %w", err)
	}
	var mw struct {
		Nets []MeshNet `json:"nets"`
	}
	if err := json.Unmarshal(mb, &mw); err != nil {
		return c, fmt.Errorf("meshes json: %w", err)
	}
	c.Meshes = mw.Nets

	epPath := filepath.Join(inventoryRoot, "endpoints", "e01.json")
	eb, err := os.ReadFile(epPath)
	if err != nil {
		return c, fmt.Errorf("endpoints: %w", err)
	}
	var ew struct {
		Endpoints []EndpointBind `json:"endpoints"`
	}
	if err := json.Unmarshal(eb, &ew); err != nil {
		return c, fmt.Errorf("endpoints json: %w", err)
	}
	c.Endpoints = ew.Endpoints

	peerDir := filepath.Join(inventoryRoot, "peers")
	entries, err := os.ReadDir(peerDir)
	if err != nil {
		return c, fmt.Errorf("peers: %w", err)
	}
	var names []string
	for _, e := range entries {
		if !e.IsDir() && filepath.Ext(e.Name()) == ".json" {
			names = append(names, e.Name())
		}
	}
	sort.Strings(names)
	for _, name := range names {
		b, err := os.ReadFile(filepath.Join(peerDir, name))
		if err != nil {
			return c, err
		}
		var peer Peer
		if err := json.Unmarshal(b, &peer); err != nil {
			return c, fmt.Errorf("%s: %w", name, err)
		}
		c.Peers = append(c.Peers, peer)
	}
	return c, nil
}
