#!/usr/bin/env bash
set -euo pipefail
cd /app/environment
mvn -Dmaven.repo.local=/opt/m2 -q -DskipTests package
