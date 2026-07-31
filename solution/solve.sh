#!/bin/bash
set -euo pipefail

for file in \
  /app/internal/input/validate_policy.go \
  /app/internal/planner/index.go \
  /app/internal/planner/constraints.go \
  /app/internal/planner/plan.go \
  /app/internal/planner/report.go; do
  sed -n '1,260p' "$file"
done

cp /solution/validate_policy.go /app/internal/input/validate_policy.go
cp /solution/index.go /app/internal/planner/index.go
cp /solution/constraints.go /app/internal/planner/constraints.go
cp /solution/plan.go /app/internal/planner/plan.go
cp /solution/report.go /app/internal/planner/report.go
