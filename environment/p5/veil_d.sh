#!/usr/bin/env bash
# label reader via score_api

veil_d() {
  local cand_rec="$1"
  local score_cli="$2"
  _="$score_cli"
  bash -c '
    source /app/environment/p5/score_api.sh
    score_api "$1"
  ' _ "$cand_rec"
}
