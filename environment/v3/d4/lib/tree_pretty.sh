#!/bin/bash

tree_pretty() {
  local src="$1"
  if [ -f "$src" ]; then
    awk 'NR>1 {print $1}' "$src" | head -n 3
  fi
}
