#!/usr/bin/env bash
set -euo pipefail
command -v dot
echo 'digraph G { a -> b }' | dot -Tsvg > /dev/null
echo graph-smoke-ok
