#!/bin/bash
QUERY="${1:-/app/answer.sparql}"
exec python3 /app/bin/run_sparql.py "$QUERY"
