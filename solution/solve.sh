#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE="/solution/analysis_correct.R"
if [ ! -f "$SOURCE" ]; then
  SOURCE="$SCRIPT_DIR/analysis_correct.R"
fi
cp "$SOURCE" /app/analysis.R
chmod 644 /app/analysis.R
