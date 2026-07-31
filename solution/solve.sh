#!/bin/bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cp "$DIR/answer_correct.sparql" /app/answer.sparql
/app/bin/runquery.sh /app/answer.sparql > /dev/null
