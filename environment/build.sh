#!/bin/bash
set -euo pipefail

cd /app
mkdir -p /app/bin
go build -buildvcs=false -trimpath -o /app/bin/drainwave .
