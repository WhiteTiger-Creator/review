#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 /path/to/output-root" >&2
  exit 64
fi

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
build_dir="$root/.engine-build"
driver="$build_dir/termatrix-driver"
mkdir -p "$build_dir"

needs_build=0
if [ ! -x "$driver" ]; then
  needs_build=1
else
  for source in "$root"/engine/*.cpp "$root"/engine/*.hpp "$root"/scripts/build_matrix.sh; do
    if [ "$source" -nt "$driver" ]; then
      needs_build=1
      break
    fi
  done
fi

if [ "$needs_build" -eq 1 ]; then
  c++ -std=c++17 -O0 -Wall -Wextra -pedantic "$root"/engine/*.cpp -o "$driver"
fi
exec "$driver" run "$root" "$1"
