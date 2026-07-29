#!/bin/bash
set -euo pipefail

for module in cli pipeline scoring cleaning; do
    cp "/solution/oracle/${module}.lua" "/app/src/${module}.lua"
done

mkdir -p /app/output
lua /app/mock_model/server.lua /app/config/model_profiles.json 18080 >/tmp/memscope-model.log 2>&1 &
MODEL_PID=$!
trap 'kill "$MODEL_PID" 2>/dev/null || true' EXIT

for _ in $(seq 1 100); do
    if lua -e 'local s=require("socket"); local c=s.tcp(); c:settimeout(0.1); local ok=c:connect("127.0.0.1",18080); c:close(); if not ok then os.exit(1) end'; then
        break
    fi
    sleep 0.05
done

/app/bin/memscope audit --config /app/config/audit.json
