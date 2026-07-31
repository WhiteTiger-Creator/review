#!/bin/bash
set -euo pipefail

SRC="$(dirname "$0")/answer_correct.cypher"
cp "$SRC" /app/answer.cypher

OUT="$(python3 /app/bin/run_query.py /app/answer.cypher)"
if [ -z "$OUT" ]; then
  echo "solve.sh: query produced no output" >&2
  exit 1
fi

ROWS="$(printf '%s\n' "$OUT" | tail -n +2 | grep -c .)"
if [ "$ROWS" -lt 2 ]; then
  echo "solve.sh: query returned $ROWS rows" >&2
  exit 1
fi

echo "solve.sh: wrote /app/answer.cypher, $ROWS rows"
