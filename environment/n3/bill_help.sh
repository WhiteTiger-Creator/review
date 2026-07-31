#!/usr/bin/env bash
# decoy advisory probe writer

bill_help() {
  local spend_tok="$1"
  mkdir -p /app/output/probe
  printf '{"advisory_spend":%s,"status":"green"}\n' "$spend_tok" \
    >/app/output/probe/bill_help.json
}
