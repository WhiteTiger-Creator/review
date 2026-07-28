#!/bin/bash
set -euo pipefail

app=/app/environment
out=/app/output
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for required in \
  "$app/go.mod" \
  "$app/vendor_tree/graph.json" \
  "$app/docs/slice_contract.md" \
  "$ROOT_DIR/files/pkg/replace/resolve.go" \
  "$ROOT_DIR/files/pkg/fingerprint/input.go" \
  "$ROOT_DIR/files/pkg/plan/optimizer.go"; do
  test -f "$required"
done

python3 -c '
from pathlib import Path
path = Path("/app/environment/pkg/tags/match.go")
text = path.read_text()
old = """\t\t\tif strings.HasPrefix(term, \"!\") {\n\t\t\t\tname := strings.TrimPrefix(term, \"!\")\n\t\t\t\tif !s.disabled[name] {\n\t\t\t\t\tmatched = false\n\t\t\t\t\tbreak\n\t\t\t\t}\n"""
new = """\t\t\tif strings.HasPrefix(term, \"!\") {\n\t\t\t\tname := strings.TrimPrefix(term, \"!\")\n\t\t\t\tif name == \"\" {\n\t\t\t\t\treturn false, fmt.Errorf(\"empty negated package tag term\")\n\t\t\t\t}\n\t\t\t\tif s.enabled[name] {\n\t\t\t\t\tmatched = false\n\t\t\t\t\tbreak\n\t\t\t\t}\n"""
if old not in text:
    raise SystemExit("starter tag matcher no longer has the expected incomplete branch")
path.write_text(text.replace(old, new, 1))
'
install -D -m 0644 "$ROOT_DIR/files/pkg/replace/resolve.go" "$app/pkg/replace/resolve.go"
install -D -m 0644 "$ROOT_DIR/files/pkg/fingerprint/input.go" "$app/pkg/fingerprint/input.go"
install -D -m 0644 "$ROOT_DIR/files/pkg/plan/optimizer.go" "$app/pkg/plan/optimizer.go"

gofmt -w \
  "$app/pkg/tags/match.go" \
  "$app/pkg/replace/resolve.go" \
  "$app/pkg/fingerprint/input.go" \
  "$app/pkg/plan/optimizer.go"

cd "$app"
go test ./...
go vet ./...
go build -trimpath -o /tmp/buildslice-oracle ./cmd/slice

mkdir -p "$out"
rm -f \
  "$out/buildslice_report.json" \
  "$out/buildslice_cache.json" \
  "$out/buildslice_run.json"

cd /app
go run /app/environment/cmd/slice \
  --all-scenarios \
  --write /app/output/buildslice_report.json

test -s "$out/buildslice_report.json"
test -s "$out/buildslice_cache.json"
test -s "$out/buildslice_run.json"
cp "$out/buildslice_report.json" /tmp/buildslice-report.cold
cp "$out/buildslice_cache.json" /tmp/buildslice-cache.cold

go run /app/environment/cmd/slice \
  --all-scenarios \
  --write /app/output/buildslice_report.json

cmp /tmp/buildslice-report.cold "$out/buildslice_report.json"
cmp /tmp/buildslice-cache.cold "$out/buildslice_cache.json"
