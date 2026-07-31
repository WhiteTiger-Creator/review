#!/usr/bin/env bash
# lane wrapper: walk + veil

source /app/environment/p5/walk_c.sh
source /app/environment/p5/veil_d.sh

lane_w_order() {
  walk_c "$1" "$2"
}

lane_w_score() {
  veil_d "$1" "$2"
}
