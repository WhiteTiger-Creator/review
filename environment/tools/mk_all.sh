#!/usr/bin/env bash
set -euo pipefail
cd /app/environment
make -C /app/environment all
mkdir -p /app/output /app/var /app/bin
