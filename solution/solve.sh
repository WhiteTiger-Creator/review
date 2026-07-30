#!/bin/bash
# Oracle: build the probe-based solver and use it to recover the retention
# policy from the sealed daemon, writing decisions for the audit request set to
# /app/out/decisions.json.
#
# This does not embed the policy. It runs the same black-box discovery an agent
# must perform: probe the sealed daemon, characterize the decision surface, and
# generalize to the full request set.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p /app/out

rustc -O "$here/solver.rs" -o /tmp/solver
/tmp/solver

echo "wrote /app/out/decisions.json"
