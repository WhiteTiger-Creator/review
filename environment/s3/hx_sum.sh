#!/usr/bin/env bash
# digest helpers

hx_sum_hex() {
  # first 16 lowercase hex of sha256 over stdin
  sha256sum | awk '{print substr($1,1,16)}'
}

hx_sum_of_file() {
  local p="$1"
  sha256sum "$p" | awk '{print substr($1,1,16)}'
}

hx_sum_of_str() {
  local s="$1"
  printf '%s' "$s" | hx_sum_hex
}
