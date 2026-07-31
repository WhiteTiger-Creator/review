#!/usr/bin/env bash
# column edit emitter

mut_a() {
  local src_rec="$1"
  local cand_dir="$2"
  local meta_tok="$3"
  _="$meta_tok"
  mkdir -p "$cand_dir"
  local i=0
  local keys
  keys=$(echo "$src_rec" | jq -r '.cols | to_entries[] | select(.value.mut == false) | .key')
  local vals=(-10 -2 0 2 3 4 5)
  local k v
  for k in $keys; do
    for v in "${vals[@]}"; do
      local cur
      cur=$(echo "$src_rec" | jq -r --arg k "$k" '.cols[$k].v')
      if awk -v a="$cur" -v b="$v" 'BEGIN{exit !(a==b)}'; then
        continue
      fi
      echo "$src_rec" | jq -c --arg k "$k" --argjson v "$v" \
        '.cols[$k].v = $v' >"$cand_dir/c_${i}.json"
      i=$((i + 1))
    done
  done
}
