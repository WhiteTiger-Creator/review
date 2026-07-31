#!/usr/bin/env bash
# lane wrapper: billing only

source /app/environment/n3/bill_b.sh

lane_v() {
  bill_b "$1" "$2"
}
