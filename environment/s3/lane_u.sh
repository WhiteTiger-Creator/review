#!/usr/bin/env bash
# lane wrapper: mutation only

source /app/environment/m7/mut_a.sh

lane_u() {
  mut_a "$1" "$2" "$3"
}
