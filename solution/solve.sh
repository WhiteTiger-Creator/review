#!/usr/bin/env bash
set -euo pipefail

cp /solution/main.go /app/task_file/cmd/partitionplan/main.go
cd /app/task_file
go build -o /app/task_file/partitionplan ./cmd/partitionplan
mkdir -p /app/task_file/out
/app/task_file/partitionplan /app/task_file/fixtures/public /app/task_file/out/partition-plan.json
