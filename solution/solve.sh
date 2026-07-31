#!/bin/bash
set -euo pipefail

cp /solution/src/features.ts /app/src/features.ts
cp /solution/src/model.ts /app/src/model.ts
cp /solution/src/metrics.ts /app/src/metrics.ts
cp /solution/src/score.ts /app/src/score.ts
cp /solution/src/reproduce.ts /app/src/reproduce.ts

cd /app
npx tsc
npm run reproduce
