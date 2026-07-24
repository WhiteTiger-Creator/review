#!/usr/bin/env bash
set -euo pipefail
export PATH="/usr/local/go/bin:${PATH}"
APP=/app/environment

python3 <<'PY'
from pathlib import Path

app = Path("/app/environment")

def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"missing snippet in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")

def replace_all(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"missing snippet in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")

ingest = app / "internal/topology/ingest.go"
replace_once(
    ingest,
    "\tgraphDirected := !strings.EqualFold(doc.Graph.EdgeDefault, \"undirected\")",
    "\tfieldByID := make(map[string]string, len(doc.Keys))\n\tfor _, key := range doc.Keys {\n\t\tif key.ID != \"\" && key.AttrName != \"\" {\n\t\t\tfieldByID[key.ID] = key.AttrName\n\t\t}\n\t}\n\n\tgraphDirected := !strings.EqualFold(doc.Graph.EdgeDefault, \"undirected\")",
)
replace_all(ingest, "\t\t\tattrName := data.Key", "\t\t\tattrName := fieldByID[data.Key]")
replace_once(
    ingest,
    '\t\tcollapseKey := src + "|" + tgt',
    '\t\tcollapseKey := fmt.Sprintf("%s|%s|%s|%s|%s|%s|%s", edge.ID, src, tgt, edge.Environment, edge.Method, edge.Path, edge.AuthzScope)',
)
ingest_text = ingest.read_text(encoding="utf-8")
if '"fmt"' not in ingest_text:
    ingest.write_text(
        ingest_text.replace(
            "import (\n\t\"encoding/xml\"",
            "import (\n\t\"encoding/xml\"\n\t\"fmt\"",
            1,
        ),
        encoding="utf-8",
    )
replace_once(
    app / "internal/precedence/authz.go",
    "func (l *Legacy) Resolve(e topology.Edge) (audiences []string, deny bool) {\n\tif len(l.GlobalAudiences) > 0 {\n\t\treturn l.GlobalAudiences, false\n\t}\n\tfor _, r := range l.EdgeRules {",
    "func (l *Legacy) Resolve(e topology.Edge) (audiences []string, deny bool) {\n\tfor _, r := range l.EdgeRules {",
)
replace_once(
    app / "internal/register/index.go",
    "\t\tstatus := strings.ToLower(record.Status)\n\t\tif _, ok := allowed[status]; !ok && status != \"accepted\" && status != \"amended\" {",
    "\t\tstatus := strings.ToLower(record.Status)\n\t\tif status == \"superseded\" || status == \"proposed\" || status == \"rejected\" {\n\t\t\tcontinue\n\t\t}\n\t\tif _, ok := allowed[status]; !ok && status != \"accepted\" && status != \"amended\" {",
)
replace_once(
    app / "internal/register/index.go",
    "\t\tif prior, ok := active[bucket]; ok {\n\t\t\tif record.Effective.After(prior.Effective) {\n\t\t\t\tactive[bucket] = record\n\t\t\t}\n\t\t} else {",
    "\t\tif prior, ok := active[bucket]; ok {\n\t\t\tif !compatible(prior, record) {\n\t\t\t\treturn nil, fmt.Errorf(\"conflicting authoritative decisions for %s\", bucket)\n\t\t\t}\n\t\t\tif rankScope(record.Scope, authority.ScopeOrder) > rankScope(prior.Scope, authority.ScopeOrder) {\n\t\t\t\tactive[bucket] = record\n\t\t\t} else if rankScope(record.Scope, authority.ScopeOrder) == rankScope(prior.Scope, authority.ScopeOrder) && record.Effective.After(prior.Effective) {\n\t\t\t\tactive[bucket] = record\n\t\t\t}\n\t\t} else {",
)
helper = '''

func rankScope(scope string, order []string) int {
\tfor i, candidate := range order {
\t\tif candidate == scope {
\t\t\treturn i
\t\t}
\t}
\treturn len(order)
}

func compatible(left, right Decision) bool {
\tif len(left.Audiences) > 0 && len(right.Audiences) > 0 && !sameAudienceList(left.Audiences, right.Audiences) {
\t\treturn false
\t}
\tif left.Issuer != "" && right.Issuer != "" && left.Issuer != right.Issuer {
\t\treturn false
\t}
\treturn true
}

func sameAudienceList(left, right []string) bool {
\tif len(left) != len(right) {
\t\treturn false
\t}
\tfor i := range left {
\t\tif left[i] != right[i] {
\t\t\treturn false
\t\t}
\t}
\treturn true
}
'''
corpus = app / "internal/register/index.go"
text = corpus.read_text(encoding="utf-8")
if "func rankScope(" not in text:
    corpus.write_text(text.replace("func Lookup(decisions map[string]Decision", helper + "func Lookup(decisions map[string]Decision", 1), encoding="utf-8")
replace_once(
    app / "internal/federation/discovery.go",
    '\tdisc.Issuer = "https://hardcoded.example.com"\n\tdisc.JWKSURI = cfg.JWKSFetch\n\tdisc.FetchURL = cfg.DiscoveryFetch',
    "\tdisc.FetchURL = cfg.DiscoveryFetch",
)
replace_once(
    app / "internal/federation/discovery.go",
    "\t\tseenKID[k.KID] = struct{}{}",
    '''\t\tif _, dup := seenKID[k.KID]; dup {
\t\t\treturn nil, nil, fmt.Errorf("duplicate kid %s", k.KID)
\t\t}
\t\tseenKID[k.KID] = struct{}{}
\t\tif _, ok := allowedKTY[k.KTY]; !ok {
\t\t\tcontinue
\t\t}
\t\tif k.Use == "enc" {
\t\t\tcontinue
\t\t}
\t\tif len(k.Ops) > 0 {
\t\t\tok := false
\t\t\tfor _, op := range k.Ops {
\t\t\t\tif op == "verify" {
\t\t\t\t\tok = true
\t\t\t\t}
\t\t\t}
\t\t\tif !ok {
\t\t\t\tcontinue
\t\t\t}
\t\t}
\t\tif strings.HasPrefix(k.ALG, "HS") || k.ALG == "NONE" {
\t\t\tcontinue
\t\t}''',
)
replace_once(
    app / "internal/trail/writer.go",
    "_, err = tx.Exec(`INSERT OR REPLACE INTO discovery_snapshot(id, run_id, issuer, jwks_uri, fetch_url, semantic_url) VALUES (1,?,?,?,?,?)`,",
    "_, err = tx.Exec(`INSERT INTO discovery_snapshot(run_id, issuer, jwks_uri, fetch_url, semantic_url) VALUES (?,?,?,?,?)`,",
)
replace_once(
    app / "internal/trail/sql/002_recursive_assertions.sql",
    "WHERE ge.denied = 0 AND pe.edge_key IS NULL;",
    "WHERE ge.denied = 0 AND (pe.edge_key IS NULL OR pe.action != 'allow');",
)
replace_once(
    app / "internal/app/config.go",
    'RuntimeDir:        getenv("MIGRATOR_RUNTIME", "/tmp/migrator-runtime"),',
    'RuntimeDir:        getenv("MIGRATOR_RUNTIME", "/app/environment/.runtime"),',
)
replace_once(
    app / "internal/app/run.go",
    "\tif err := error(nil); err != nil {",
    "\tif err := writer.RunRecursiveChecks(runID); err != nil {",
)
PY

cd "$APP"
mkdir -p bin
CGO_ENABLED=0 go build -o bin/migrate-policy ./cmd/policy-migrator
"$APP/bin/reset-state"
"$APP/bin/migrate-policy"
