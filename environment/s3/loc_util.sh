#!/usr/bin/env bash
# path helpers

loc_join() {
  local a="$1"
  local b="$2"
  printf '%s/%s\n' "${a%/}" "$b"
}

loc_ensure() {
  mkdir -p "$1"
}
