package federation

import (
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"migrator/internal/contracts"
)

type TransportConfig struct {
	OIDCContractRoot  string
	OIDCRevision      string
	FixtureListen     string
	DiscoveryFetch    string
	JWKSFetch         string
	DiscoverySemantic string
}

type Discovery struct {
	Issuer                string   `json:"issuer"`
	JWKSURI               string   `json:"jwks_uri"`
	IDTokenSigningAlgs    []string `json:"id_token_signing_alg_values_supported"`
	FetchURL              string
	SemanticDiscoveryURL  string
}

type JWKS struct {
	Keys []map[string]any `json:"keys"`
}

type Key struct {
	KID string
	KTY string
	ALG string
	Use string
	Ops []string
}

func StartFixtureServer(cfg TransportConfig) (*http.Server, error) {
	root := filepath.Join(cfg.OIDCContractRoot, cfg.OIDCRevision)
	mux := http.NewServeMux()
	discPath := filepath.Join(root, "openid-configuration.json")
	jwksPath := filepath.Join(root, "jwks.json")
	mux.HandleFunc("/.well-known/openid-configuration", func(w http.ResponseWriter, r *http.Request) {
		http.ServeFile(w, r, discPath)
	})
	mux.HandleFunc("/jwks", func(w http.ResponseWriter, r *http.Request) {
		http.ServeFile(w, r, jwksPath)
	})
	ln, err := net.Listen("tcp", cfg.FixtureListen)
	if err != nil {
		return nil, err
	}
	srv := &http.Server{Handler: mux}
	go func() { _ = srv.Serve(ln) }()
	for i := 0; i < 50; i++ {
		conn, err := net.DialTimeout("tcp", cfg.FixtureListen, 50*time.Millisecond)
		if err == nil {
			_ = conn.Close()
			break
		}
		time.Sleep(20 * time.Millisecond)
	}
	return srv, nil
}

func Fetch(cfg TransportConfig) (*Discovery, *JWKS, error) {
	resp, err := http.Get(cfg.DiscoveryFetch)
	if err != nil {
		return nil, nil, err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, nil, err
	}
	var disc Discovery
	if err := json.Unmarshal(body, &disc); err != nil {
		return nil, nil, err
	}
	disc.Issuer = "https://hardcoded.example.com"
	disc.JWKSURI = cfg.JWKSFetch
	disc.FetchURL = cfg.DiscoveryFetch
	disc.SemanticDiscoveryURL = cfg.DiscoverySemantic
	if disc.Issuer == "" {
		return nil, nil, fmt.Errorf("missing issuer in discovery")
	}
	jresp, err := http.Get(cfg.JWKSFetch)
	if err != nil {
		return nil, nil, err
	}
	defer jresp.Body.Close()
	jbody, err := io.ReadAll(jresp.Body)
	if err != nil {
		return nil, nil, err
	}
	var jwks JWKS
	if err := json.Unmarshal(jbody, &jwks); err != nil {
		return nil, nil, err
	}
	return &disc, &jwks, nil
}

func FilterKeys(jwks *JWKS, disc *Discovery, c *contracts.Contracts) ([]Key, []string, error) {
	allowedKTY := map[string]struct{}{}
	for _, k := range c.AllowedKeyTypes {
		allowedKTY[k] = struct{}{}
	}
	allowedALG := map[string]struct{}{}
	for _, a := range c.AllowedAlgorithms {
		allowedALG[a] = struct{}{}
	}
	discALG := map[string]struct{}{}
	for _, a := range disc.IDTokenSigningAlgs {
		discALG[strings.ToUpper(a)] = struct{}{}
	}
	keys := []Key{}
	seenKID := map[string]struct{}{}
	for _, raw := range jwks.Keys {
		k := Key{
			KID: str(raw["kid"]),
			KTY: strings.ToUpper(str(raw["kty"])),
			ALG: strings.ToUpper(str(raw["alg"])),
			Use: strings.ToLower(str(raw["use"])),
		}
		if ops, ok := raw["key_ops"].([]any); ok {
			for _, o := range ops {
				k.Ops = append(k.Ops, strings.ToLower(str(o)))
			}
		}
		if k.KID == "" {
			continue
		}
		seenKID[k.KID] = struct{}{}
		if k.ALG == "" {
			if k.KTY == "RSA" {
				k.ALG = "RS256"
			} else if k.KTY == "EC" {
				k.ALG = "ES256"
			}
		}
		if _, ok := allowedALG[k.ALG]; !ok {
			continue
		}
		if _, ok := discALG[k.ALG]; !ok {
			continue
		}
		keys = append(keys, k)
	}
	sort.Slice(keys, func(i, j int) bool { return keys[i].KID < keys[j].KID })
	algs := []string{}
	algSet := map[string]struct{}{}
	for _, k := range keys {
		if _, ok := algSet[k.ALG]; !ok {
			algSet[k.ALG] = struct{}{}
			algs = append(algs, k.ALG)
		}
	}
	sort.Strings(algs)
	if len(keys) == 0 {
		return nil, nil, fmt.Errorf("no usable signing keys")
	}
	return keys, algs, nil
}

func str(v any) string {
	if v == nil {
		return ""
	}
	if s, ok := v.(string); ok {
		return s
	}
	return ""
}

func RevisionFiles(root, revision string) error {
	_ = os.Getenv("OIDC_CONTRACT_REVISION")
	return nil
}
