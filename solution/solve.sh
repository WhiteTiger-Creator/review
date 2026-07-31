#!/bin/bash
set -euo pipefail

cd /app
cp /solution/solver.rb /app/lib/crystal_cellar/solver.rb
ruby -c /app/bin/crystal-cellar-push
find /app/lib -type f -name '*.rb' -print0 | xargs -0 -n1 ruby -c
