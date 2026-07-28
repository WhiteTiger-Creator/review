package app

import "os"

type Config struct {
	GraphPath          string
	LegacyPath         string
	DossierRoot        string
	CanonicalRoot      string
	AuthorityRoot      string
	OIDCContractRoot   string
	OIDCRevision       string
	FixtureListen      string
	DiscoverySemantic  string
	DiscoveryFetch     string
	JWKSFetch          string
	OutputDir          string
	RuntimeDir         string
}

func LoadConfig() Config {
	return Config{
		GraphPath:         getenv("GRAPH_PATH", "/app/environment/input/service-callgraph.graphml"),
		LegacyPath:        getenv("LEGACY_AUTHZ_PATH", "/app/environment/input/legacy-authz.yaml"),
		DossierRoot:       getenv("DOSSIER_ROOT", "/app/environment/dossier"),
		CanonicalRoot:     getenv("CANONICAL_ROOT", "/data/canonical"),
		AuthorityRoot:     getenv("DOSSIER_AUTHORITY_ROOT", "/data/dossier-authority"),
		OIDCContractRoot:  getenv("OIDC_CONTRACT_ROOT", "/data/oidc-contracts"),
		OIDCRevision:      getenv("OIDC_CONTRACT_REVISION", "google-revision-a"),
		FixtureListen:     getenv("OIDC_FIXTURE_LISTEN", "127.0.0.1:18081"),
		DiscoverySemantic: getenv("OIDC_DISCOVERY_SEMANTIC_URL", "https://accounts.google.com/.well-known/openid-configuration"),
		DiscoveryFetch:    getenv("OIDC_DISCOVERY_FETCH_URL", "http://127.0.0.1:18081/.well-known/openid-configuration"),
		JWKSFetch:         getenv("OIDC_JWKS_FETCH_OVERRIDE", "http://127.0.0.1:18081/jwks"),
		OutputDir:         getenv("OUTPUT_DIR", "/output"),
		RuntimeDir:        getenv("MIGRATOR_RUNTIME", "/tmp/migrator-runtime"),
	}
}

func getenv(k, d string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return d
}
