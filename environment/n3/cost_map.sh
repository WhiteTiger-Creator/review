#!/usr/bin/env bash
# field width table reader

cost_map_w() {
  local rec_json="$1"
  local key_tok="$2"
  echo "$rec_json" | jq -r --arg k "$key_tok" '.cols[$k].w'
}
