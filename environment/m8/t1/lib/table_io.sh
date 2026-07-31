#!/bin/bash

read_rank_weight() {
  local layer="$1"
  local rank_path="$2"
  awk -v L="$layer" '!/^#/ && NF>=2 && $1==L {print $2; exit}' "$rank_path"
}

load_frag_map() {
  local frag_path="$1"
  awk 'NF>=2 {print $1 "\t" $2}' "$frag_path"
}
