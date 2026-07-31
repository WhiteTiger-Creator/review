#!/bin/bash
set -e

SOLUTION_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SOLUTION_DIR/reference/solve_audit.py"
