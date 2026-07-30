#!/bin/bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path

path = Path("/app/main.go")
source = path.read_text()

replacements = [
    (
        """\
\t"fmt"
\t"log"
""",
        """\
\t"fmt"
\t"io"
\t"log"
""",
        "io import",
    ),
    (
        """\
\t\texits := w.Rooms[room].Exits
\t\tfor i := len(exits) - 1; i >= 0; i-- {
\t\t\texit := exits[i]
""",
        """\
\t\tfor _, exit := range w.Rooms[room].Exits {
""",
        "route",
    ),
    (
        "z = (z ^ (z >> 28)) * 0x94D049BB133111EB",
        "z = (z ^ (z >> 27)) * 0x94D049BB133111EB",
        "replay",
    ),
    (
        """\
\tdoor := false
\tfor _, e := range s.world.Rooms[sess.Room].Exits {
\t\tif e == to {
\t\t\tdoor = true
\t\t\tbreak
\t\t}
\t}
\tif !door {
\t\twriteErr(w, http.StatusConflict, "no-door")
\t\treturn
\t}
\ttarget, ok := s.world.Rooms[to]
\tif !ok {
\t\twriteErr(w, http.StatusConflict, "unknown-room")
\t\treturn
\t}
\tif target.Lock != "" && !sess.has("key."+target.Lock) {
\t\twriteErr(w, http.StatusConflict, "locked")
\t\treturn
\t}
\tif target.Dark && !sess.has("torch") {
\t\twriteErr(w, http.StatusConflict, "dark")
\t\treturn
\t}
""",
        """\
\ttarget, ok := s.world.Rooms[to]
\tif !ok {
\t\twriteErr(w, http.StatusConflict, "unknown-room")
\t\treturn
\t}
\tdoor := false
\tfor _, e := range s.world.Rooms[sess.Room].Exits {
\t\tif e == to {
\t\t\tdoor = true
\t\t\tbreak
\t\t}
\t}
\tif !door {
\t\twriteErr(w, http.StatusConflict, "no-door")
\t\treturn
\t}
\tif target.Lock != "" && !sess.has("key."+target.Lock) {
\t\twriteErr(w, http.StatusConflict, "locked")
\t\treturn
\t}
""",
        "movement",
    ),
    (
        "seq := len(s.history[sess.ID])",
        "seq := len(s.history[sess.ID]) + 1",
        "journal",
    ),
    (
        """\
\tif err := json.NewDecoder(r.Body).Decode(&body); err != nil {
\t\treturn "", false
\t}
\tv, ok := body[field].(string)
""",
        """\
\tdecoder := json.NewDecoder(r.Body)
\tif err := decoder.Decode(&body); err != nil {
\t\treturn "", false
\t}
\tif len(body) != 1 {
\t\treturn "", false
\t}
\tvar trailing any
\tif err := decoder.Decode(&trailing); err != io.EOF {
\t\treturn "", false
\t}
\tv, ok := body[field].(string)
""",
        "strict request body",
    ),
]

for old, new, name in replacements:
    if source.count(old) != 1:
        raise SystemExit(f"oracle: expected {name} defect not found exactly once")
    source = source.replace(old, new)
path.write_text(source)
PY

cd /app
gofmt -w main.go
go build -o /tmp/dungeond-oracle-check .

ORACLE_ADDR=127.0.0.1:18383
ORACLE_URL="http://$ORACLE_ADDR"
ORACLE_DB=/app/data/dungeon.db
ORACLE_LOG=/tmp/dungeond-oracle.log
mkdir -p /app/data

/tmp/dungeond-oracle-check \
    -addr "$ORACLE_ADDR" \
    -db "$ORACLE_DB" \
    -compose /app/world/docker-compose.yml \
    >"$ORACLE_LOG" 2>&1 &
SERVER_PID=$!

cleanup() {
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT

READY=false
for _ in $(seq 1 50); do
    if curl -sf "$ORACLE_URL/world" >/dev/null 2>&1; then
        READY=true
        break
    fi
    sleep 0.2
done
if [ "$READY" != true ]; then
    echo "oracle: server did not become ready" >&2
    cat "$ORACLE_LOG" >&2
    exit 1
fi

SID=$(curl -sf -X POST "$ORACLE_URL/sessions" | sed -E 's/.*"id":"([^"]+)".*/\1/')
if [ -z "$SID" ]; then
    echo "oracle: session creation returned no id" >&2
    exit 1
fi

curl -sf -H 'Content-Type: application/json' -X POST -d '{"to":"courtyard"}' "$ORACLE_URL/sessions/$SID/move" >/dev/null
curl -sf -H 'Content-Type: application/json' -X POST -d '{"item":"key.iron"}' "$ORACLE_URL/sessions/$SID/take" >/dev/null
curl -sf -H 'Content-Type: application/json' -X POST -d '{"to":"chapel"}' "$ORACLE_URL/sessions/$SID/move" >/dev/null
curl -sf -H 'Content-Type: application/json' -X POST -d '{"item":"key.gold"}' "$ORACLE_URL/sessions/$SID/take" >/dev/null
FINAL_STATE=$(curl -sf -H 'Content-Type: application/json' -X POST -d '{"to":"vault"}' "$ORACLE_URL/sessions/$SID/move")
if [[ "$FINAL_STATE" != *'"won":true'* ]]; then
    echo "oracle: playthrough did not produce a winning run: $FINAL_STATE" >&2
    exit 1
fi

cleanup
trap - EXIT
