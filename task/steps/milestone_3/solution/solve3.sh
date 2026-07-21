#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp "$ROOT_DIR/oracle_app.js" /app/www/app.js
