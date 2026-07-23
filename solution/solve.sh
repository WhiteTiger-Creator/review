#!/bin/bash
set -euo pipefail

install -m 0644 /solution/judge.f90 /app/src/judge.f90
make -C /app clean
make -C /app
test -x /app/hexverdict
