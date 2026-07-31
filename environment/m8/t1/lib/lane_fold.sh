#!/bin/bash

lane_fold() {
  local src="$1"
  local n=0
  if [ -f "$src" ]; then
    n="$(wc -l < "$src" | tr -d ' ')"
  fi
  printf 'lane_lines=%s\n' "$n"
}
