package policy

import (
	"fmt"
	"os"
	"sort"
	"strings"

	"gopkg.in/yaml.v3"

	"migrator/internal/contracts"
	"migrator/internal/register"
	"migrator/internal/topology"
	"migrator/internal/precedence"
	"migrator/internal/federation"
)

type EdgePolicy struct {
	EdgeID      string   `yaml:"edge_id"`
	Source      string   `yaml:"source"`
	Target      string   `yaml:"target"`
	Environment string   `yaml:"environment"`
	Method      string   `yaml:"method"`
	Path        string   `yaml:"path"`
	AuthzScope  string   `yaml:"authz_scope"`
	Action      string   `yaml:"action"`
	Issuer      string   `yaml:"issuer,omitempty"`
	JWKSURI     string   `yaml:"jwks_uri,omitempty"`
	Audiences   []string `yaml:"audiences,omitempty"`
	Algorithms  []string `yaml:"algorithms,omitempty"`
	KeyIDs      []string `yaml:"allowed_key_ids,omitempty"`
	Provenance  []string `yaml:"provenance,omitempty"`
}

type Bundle struct {
	SchemaVersion int                    `yaml:"schema_version"`
	Issuers       map[string]IssuerBlock `yaml:"issuers"`
	Edges         []EdgePolicy           `yaml:"edges"`
	Metadata      map[string]any         `yaml:"metadata,omitempty"`
}

type IssuerBlock struct {
	Issuer     string   `yaml:"issuer"`
	JWKSURI    string   `yaml:"jwks_uri"`
	Algorithms []string `yaml:"algorithms"`
}

type Input struct {
	Graph     *topology.Graph
	Legacy    *precedence.Legacy
	Decisions map[string]register.Decision
	Discovery *federation.Discovery
	Keys      []federation.Key
	Algs      []string
	Contracts *contracts.Contracts
}

func Build(in Input) (*Bundle, error) {
	issuer := in.Discovery.Issuer
	jwksURI := in.Discovery.JWKSURI
	algs := append([]string{}, in.Algs...)
	sort.Strings(algs)
	bundle := &Bundle{
		SchemaVersion: 2,
		Issuers: map[string]IssuerBlock{
			issuer: {Issuer: issuer, JWKSURI: jwksURI, Algorithms: algs},
		},
		Metadata: map[string]any{"migration": "mtls-to-oidc"},
	}
	for _, e := range in.Graph.Edges {
		if e.Denied {
			bundle.Edges = append(bundle.Edges, EdgePolicy{
				EdgeID: topology.EdgeKey(e), Source: e.Source, Target: e.Target,
				Environment: e.Environment, Method: e.Method, Path: e.Path, AuthzScope: e.AuthzScope,
				Action: "deny", Provenance: []string{"graph:denied"},
			})
			continue
		}
		aud, deny := in.Legacy.Resolve(e)
		if deny {
			bundle.Edges = append(bundle.Edges, EdgePolicy{
				EdgeID: topology.EdgeKey(e), Source: e.Source, Target: e.Target,
				Environment: e.Environment, Method: e.Method, Path: e.Path, AuthzScope: e.AuthzScope,
				Action: "deny", Provenance: []string{"legacy:deny"},
			})
			continue
		}
		dec := register.Lookup(in.Decisions, e)
		if dec != nil && strings.EqualFold(dec.Status, "rejected") {
			return nil, fmt.Errorf("rejected decision for edge %s", topology.EdgeKey(e))
		}
		edgeIssuer := issuer
		edgeAlgs := append([]string{}, algs...)
		var keyIDs []string
		prov := []string{"graph", "legacy"}
		if dec != nil {
			prov = append(prov, "dossier:"+dec.ID)
			if dec.Issuer != "" {
				if dec.Issuer != issuer {
					return nil, fmt.Errorf("issuer mismatch for %s", topology.EdgeKey(e))
				}
				edgeIssuer = dec.Issuer
			}
			if len(dec.Audiences) > 0 {
				aud = dec.Audiences
			}
			if len(dec.Algorithms) > 0 {
				edgeAlgs = intersect(edgeAlgs, dec.Algorithms)
			}
			keyIDs = dec.KeyIDs
		}
		if len(edgeAlgs) == 0 {
			return nil, fmt.Errorf("no algorithms for edge %s", topology.EdgeKey(e))
		}
		bundle.Edges = append(bundle.Edges, EdgePolicy{
			EdgeID: topology.EdgeKey(e), Source: e.Source, Target: e.Target,
			Environment: e.Environment, Method: e.Method, Path: e.Path, AuthzScope: e.AuthzScope,
			Action: "allow", Issuer: edgeIssuer, JWKSURI: jwksURI, Audiences: aud,
			Algorithms: edgeAlgs, KeyIDs: keyIDs, Provenance: prov,
		})
	}
	sort.Slice(bundle.Edges, func(i, j int) bool { return bundle.Edges[i].EdgeID < bundle.Edges[j].EdgeID })
	return bundle, nil
}

func intersect(a, b []string) []string {
	set := map[string]struct{}{}
	for _, x := range a {
		set[x] = struct{}{}
	}
	out := []string{}
	for _, x := range b {
		if _, ok := set[x]; ok {
			out = append(out, x)
		}
	}
	sort.Strings(out)
	return out
}

func WriteYAML(path string, bundle *Bundle) error {
	raw, err := yaml.Marshal(bundle)
	if err != nil {
		return err
	}
	text := string(raw)
	for _, retired := range []string{"client_cert_subject", "ca_bundle", "serial_number", "mtls_trust_bundle"} {
		if strings.Contains(text, retired) {
			return fmt.Errorf("retired field leaked: %s", retired)
		}
	}
	return os.WriteFile(path, raw, 0o644)
}
