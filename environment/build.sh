#!/bin/bash
set -euo pipefail
cd /app
mapfile -t SRC < <(find src -name '*.kt' | sort)
kotlinc "${SRC[@]}" -include-runtime -d engine.jar
