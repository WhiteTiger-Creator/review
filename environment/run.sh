#!/bin/bash
set -euo pipefail
exec java -jar /app/engine.jar "$@"
