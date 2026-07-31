#!/bin/bash

name_list() {
  local dir_path="$1"
  local n=0
  if [ -d "$dir_path" ]; then
    n="$(find "$dir_path" -maxdepth 1 -type f | wc -l | tr -d ' ')"
  fi
  printf 'name_count=%s\n' "$n"
}
