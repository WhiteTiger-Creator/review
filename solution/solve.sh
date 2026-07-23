#!/bin/bash
set -euo pipefail

if [ -f /solution/workload_gate.go ]; then
    cp /solution/workload_gate.go /app/workload_gate.go
else
    cp solution/workload_gate.go /app/workload_gate.go
fi

/usr/local/go/bin/gofmt -w /app/workload_gate.go
/usr/local/go/bin/go build -o /tmp/workload-gate /app/workload_gate.go
/tmp/workload-gate /app/task_file/input_data /app/task_file/output_data
