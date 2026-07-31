#!/usr/bin/env bash
# JSON IO helpers

jio_read() {
  local p="$1"
  cat "$p"
}

jio_write() {
  local p="$1"
  local body="$2"
  mkdir -p "$(dirname "$p")"
  printf '%s\n' "$body" >"$p"
}

jio_canon() {
  local p="$1"
  jq -c -S '.' "$p"
}
