#!/usr/bin/env bash
set -euo pipefail

GRADLE_USER_HOME="${GRADLE_USER_HOME:-/tmp/graphrun-gradle}"
GRADLE_BIN="${GRADLE_BIN:-/opt/gradle/bin/gradle}"
CACHE_TEMPLATE="${GRADLE_CACHE_TEMPLATE:-/opt/gradle-cache-template}"

if [[ ! -d "${GRADLE_USER_HOME}/caches" && -d "${CACHE_TEMPLATE}" ]]; then
  echo "Seeding Gradle user home from ${CACHE_TEMPLATE}"
  mkdir -p "${GRADLE_USER_HOME}"
  cp -a "${CACHE_TEMPLATE}/." "${GRADLE_USER_HOME}/"
fi

build_project() {
  local project_dir="$1"
  if [[ ! -d "${project_dir}" ]]; then
    echo "Skipping missing project: ${project_dir}"
    return 0
  fi
  echo "Building ${project_dir}"
  "${GRADLE_BIN}" \
    --project-dir "${project_dir}" \
    --no-daemon \
    --offline \
    clean test assemble
}

build_project "/app/pkg"
build_project "/app/release-mirror"

echo "Offline build complete"
