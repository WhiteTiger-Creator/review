#!/usr/bin/env bash
set -euo pipefail

CASE_PATH="${1:-/app/environment/fixtures/f01.json}"
cd /app/environment
mvn -Dmaven.repo.local=/opt/m2 -q -DskipTests package
java -jar /app/environment/target/culvert-pipeline.jar "${CASE_PATH}"
