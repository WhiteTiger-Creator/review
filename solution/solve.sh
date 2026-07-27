#!/bin/bash
set -euo pipefail
install -m 0644 /solution/reference/internal/game/validate.go /app/internal/game/validate.go
install -m 0644 /solution/reference/internal/game/resolve.go /app/internal/game/resolve.go
install -m 0644 /solution/reference/internal/game/digest.go /app/internal/game/digest.go
/app/bin/build-tidefront
rm -f /output/oracle-game.json
/app/bin/tidefront adjudicate \
  --match /app/examples/game/match.json \
  --stations /app/examples/game/stations.json \
  --catalog /app/examples/game/catalog \
  --leaps /app/examples/game/leaps.txt \
  --threads 2 \
  --output /output/oracle-game.json
