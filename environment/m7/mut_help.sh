#!/usr/bin/env bash
# decoy pretty-printer

mut_help() {
  local a_json="$1"
  local b_json="$2"
  mkdir -p /app/output/probe
  {
    echo "diff_keys:"
    echo "$a_json" | jq -r '.cols | keys[]'
    echo "$b_json" | jq -r '.cols | keys[]'
  } >/app/output/probe/mut_help.txt
}
