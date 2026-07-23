#!/bin/bash
set -euo pipefail

install -m 0644 /solution/oracle.janet /app/src/main.janet
janet /app/src/main.janet /app/input /app/output
