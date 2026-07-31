#!/bin/bash

digest16() {
  local a="$1"
  local b="$2"
  local c="$3"
  printf '%s|%s|%s' "$a" "$b" "$c" | sha256sum | awk '{print substr($1,1,16)}'
}

read_gen_hosts() {
  local gen_path="$1"
  awk -F'|' '{print $1 "\t" $2}' "$gen_path"
}

mesh_stamp_for() {
  local host="$1"
  local mesh_path="$2"
  awk -v h="$host" 'NR>1 && $1==h {print $2; exit}' "$mesh_path"
}
