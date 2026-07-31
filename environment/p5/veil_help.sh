#!/usr/bin/env bash
# decoy raw scorer bypass

veil_help() {
  local cand_rec="$1"
  source /app/environment/p5/score_api.sh
  score_api "$cand_rec"
}
