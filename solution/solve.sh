#!/bin/bash
set -euo pipefail

cat > /app/environment/m7/mut_a.sh << 'EOF'
#!/usr/bin/env bash
# emit schema-legal candidate variants on mutable columns only

mut_a() {
  local src_rec="$1"
  local cand_dir="$2"
  local meta_tok="$3"
  _="$meta_tok"
  mkdir -p "$cand_dir"
  local i=0
  local -a keys=()
  local k
  while IFS= read -r k; do
    [ -n "$k" ] || continue
    keys+=("$k")
  done < <(echo "$src_rec" | jq -r '.cols | to_entries[] | select(.value.mut == true) | .key')

  local vals=(-10 -2 0 2 3 4 5)
  local v cur
  for k in "${keys[@]}"; do
    for v in "${vals[@]}"; do
      cur=$(echo "$src_rec" | jq -r --arg k "$k" '.cols[$k].v')
      if awk -v a="$cur" -v b="$v" 'BEGIN{exit !(a==b)}'; then
        continue
      fi
      echo "$src_rec" | jq -c --arg k "$k" --argjson v "$v" \
        '.cols[$k].v = $v' >"$cand_dir/c_${i}.json"
      i=$((i + 1))
    done
  done

  # pairwise mutable edits for tighter envelopes on multi-column fixtures
  local k2 v2
  local n=${#keys[@]}
  local a b
  if [[ "$n" -ge 2 ]]; then
    for ((a=0; a<n; a++)); do
      for ((b=a+1; b<n; b++)); do
        k="${keys[$a]}"
        k2="${keys[$b]}"
        for v in 2 3 4; do
          for v2 in 0 2 3; do
            cur=$(echo "$src_rec" | jq -r --arg k "$k" '.cols[$k].v')
            local cur2
            cur2=$(echo "$src_rec" | jq -r --arg k2 "$k2" '.cols[$k2].v')
            if awk -v a="$cur" -v b="$v" 'BEGIN{exit !(a==b)}' && awk -v a="$cur2" -v b="$v2" 'BEGIN{exit !(a==b)}'; then
              continue
            fi
            echo "$src_rec" | jq -c \
              --arg k "$k" --argjson v "$v" \
              --arg k2 "$k2" --argjson v2 "$v2" \
              '.cols[$k].v = $v | .cols[$k2].v = $v2' \
              >"$cand_dir/c_${i}.json"
            i=$((i + 1))
          done
        done
      done
    done
  fi
}
EOF

cat > /app/environment/n3/bill_b.sh << 'EOF'
#!/usr/bin/env bash
# encoded wiresize spend: sum (2+w) over changed columns

bill_b() {
  local packed_blob="$1"
  local cap_tok="$2"
  local cap_num
  cap_num=$(printf '%s' "$cap_tok" | tr -cd '0-9' )
  _="$cap_num"
  local spend
  spend=$(echo "$packed_blob" | jq '
    . as $root
    | [$root.base.cols | to_entries[] as $e
      | select($e.value.v != $root.cand.cols[$e.key].v)
      | (2 + ($e.value.w | tonumber))]
    | add // 0
  ')
  # reject pathological negative parses
  if [[ -z "$spend" ]]; then
    echo 0
    return 0
  fi
  if [[ "$spend" -lt 0 ]]; then
    echo 0
    return 0
  fi
  echo "$spend"
}
EOF

cat > /app/environment/p5/walk_c.sh << 'EOF'
#!/usr/bin/env bash
# deterministic visitation order from seed

walk_c() {
  local cand_dir="$1"
  local seed_tok="$2"
  local f name key
  local -a rows=()
  shopt -s nullglob
  for f in "$cand_dir"/*.json; do
    name=$(basename "$f")
    key=$(printf '%s:%s' "$seed_tok" "$name" | sha256sum | awk '{print $1}')
    rows+=("$key $name")
  done
  shopt -u nullglob
  if [[ ${#rows[@]} -eq 0 ]]; then
    return 0
  fi
  local sorted
  sorted=$(printf '%s\n' "${rows[@]}" | LC_ALL=C sort)
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    printf '%s\n' "${line##* }"
  done <<<"$sorted"
}
EOF

cat > /app/environment/p5/veil_d.sh << 'EOF'
#!/usr/bin/env bash
# score through defense preprocessing then frozen API

veil_d() {
  local cand_rec="$1"
  local score_cli="$2"
  _="$score_cli"
  # shellcheck disable=SC1091
  source /app/environment/p5/pre_gate.sh
  # shellcheck disable=SC1091
  source /app/environment/p5/score_api.sh
  local gated lab
  gated=$(pre_gate "$cand_rec")
  if [[ -z "$gated" ]]; then
    echo 0
    return 0
  fi
  lab=$(score_api "$gated")
  if [[ -z "$lab" ]]; then
    echo 0
    return 0
  fi
  printf '%s\n' "$lab"
}
EOF

chmod +x /app/environment/m7/mut_a.sh \
  /app/environment/n3/bill_b.sh \
  /app/environment/p5/walk_c.sh \
  /app/environment/p5/veil_d.sh

bash /app/environment/cli/hx_drv.sh \
  --policy /app/environment/v1/caps_a.json \
  --cases /app/environment/k2/demo \
  --out /app/output/adv_report.json
